import os
import re
import json
import time
import feedparser
import requests
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Source definitions ────────────────────────────────────────────────────────

RSS_SOURCES = {
    # Core GenAI — official sources
    "Hacker News AI":                "https://hnrss.org/frontpage?q=AI+LLM+agent",
    "Anthropic Blog":                "https://www.anthropic.com/news/rss.xml",
    "OpenAI Blog":                   "https://openai.com/blog/rss.xml",
    "Google DeepMind":               "https://deepmind.google/blog/rss.xml",
    "LangChain Blog":                "https://blog.langchain.dev/rss/",
    "Microsoft AI Blog":             "https://blogs.microsoft.com/ai/feed/",
    "The Batch":                     "https://www.deeplearning.ai/the-batch/feed/",
    # Insurance & InsurTech
    "The Digital Insurer":           "https://the-digital-insurer.com/feed",
    "Insurance Innovation Reporter": "https://iireporter.com/feed",
    "Zelros":                        "https://zelros.com/feed",
    # Finance & FinTech AI
    "VentureBeat AI":                "https://venturebeat.com/category/ai/feed",
    "MarkTechPost":                  "https://marktechpost.com/feed",
    # Data Science & Analytics
    "KDnuggets":                     "https://www.kdnuggets.com/feed",
    "Towards Data Science":          "https://towardsdatascience.com/feed",
    "InfoQ AI/ML":                   "https://feed.infoq.com/ai-ml-data-eng/",
    "Databricks ML":                 "https://www.databricks.com/blog/category/machine-learning/feed",
    # HR & People Analytics
    "Josh Bersin":                   "https://joshbersin.com/feed",
    "MIT Sloan AI":                  "https://sloanreview.mit.edu/tag/artificial-intelligence/feed",
    # Enterprise AI use cases (implementation focus)
    "Emerj AI Research":             "https://emerj.com/feed/",
    "AI Business":                   "https://aibusiness.com/rss.xml",
}

REDDIT_SUBS = ["MachineLearning", "LocalLLaMA", "datascience"]

# ── Consultant profile for the scoring prompt ─────────────────────────────────

PROFILE = """
You are scoring news articles for a GenAI implementation consultant at a large IT company in Germany.
They build agentic workflows, RAG systems, and multi-agent pipelines for enterprise clients.
Tech stack: Azure OpenAI, LangGraph, Streamlit, Azure Container Apps, MS365.

Client domains:
- Finance and Banking (primary, current clients)
- Insurance (expanding into this)
- HR and talent management (built A-MATCH internal mobility platform)
- Data science and analytics (built a Text2SQL Data Analyst Agent)

They CARE about:
- New model releases and capability updates (GPT, Claude, Gemini)
- LangGraph and agentic framework updates
- RAG improvements and patterns (chunking, retrieval, evaluation)
- Azure AI and Microsoft AI product updates
- EU AI Act and DORA compliance developments (Germany/DACH market)
- Real production use cases and implementation patterns — especially in finance, insurance, HR
- InsurTech and FinTech AI adoption stories with concrete outcomes
- AI in HR: candidate matching, workforce analytics, skills intelligence
- Data science tooling, LLM evaluation frameworks, observability
- Practical tutorials they can apply to current projects
- Enterprise AI architecture decisions (build vs buy, multi-agent orchestration, cost control)
- Lessons learned from failed or successful AI deployments

They do NOT care about:
- Academic research papers with no practical application
- Consumer AI apps (photo filters, gaming, entertainment)
- Crypto, blockchain, or Web3 topics
- US-only regulatory news with no EU relevance
- Generic "AI will change everything" opinion pieces
- Vendor marketing with no technical substance

Scoring philosophy: Be STRICT. Prefer 5 great articles over 20 mediocre ones.
- Score 9-10: Would forward to a client or colleague today — concrete, actionable, directly applicable
- Score 7-8: Worth reading this week — relevant, practical, good signal
- Score 4-6: Tangentially related — interesting but not immediately useful
- Score 1-3: Irrelevant or noise for this consultant's work

BONUS — push score to 9-10 for:
- Production deployments in finance, insurance, or HR with measured outcomes (ROI, accuracy, adoption %)
- Architecture patterns they can reuse: RAG pipelines, agent orchestration, evaluation setups
- Client-ready business cases: risk reduction, cost savings, compliance angles
- Step-by-step tutorials with working code for LangGraph, Azure AI, or LangChain
- EU-specific regulatory guidance with concrete compliance checklists
- Comparisons of models or frameworks that directly affect their tech stack choices
"""

# ── Pydantic schema for structured LLM output ─────────────────────────────────

class Article(BaseModel):
    title: str
    url: str
    source: str
    relevance_score: int = Field(ge=1, le=10, description="1=irrelevant, 10=must-read")
    reason: str = Field(
        description="One sentence: why this matters to the consultant specifically"
    )
    summary: str = Field(
        description=(
            "2-3 sentence plain-language summary of the article, written for this consultant. "
            "Highlight the angles most relevant to their work — skip generic context."
        )
    )
    actionable_insights: list[str] = Field(
        description=(
            "2-3 concrete takeaways the consultant can act on today: "
            "things to try, reference with clients, or add to their toolkit. "
            "Each insight should be one sentence, specific, not generic."
        )
    )
    category: Literal["models", "tools", "implementation", "industry", "regulation", "tutorial"]
    domain: Literal["general", "finance", "insurance", "hr", "data-science"]
    worth_reading: bool = Field(
        description="True only if relevance_score >= 7 AND directly actionable for their work"
    )


# ── Profile loader & prompt builder ──────────────────────────────────────────

def load_profile() -> dict | None:
    """Load data/profile.json if it exists; return None to fall back to PROFILE constant."""
    profile_path = "data/profile.json"
    if not os.path.exists(profile_path):
        return None
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_profile_prompt(profile: dict) -> str:
    """Convert a profile dict into a scoring prompt string for the LLM."""
    role         = profile.get("role", "GenAI consultant")
    company_type = profile.get("company_type", "IT company")
    market       = ", ".join(profile.get("market", ["EU"])) or "EU"

    ts   = profile.get("tech_stack", {})
    llms = ", ".join(ts.get("llm_providers",  [])) or "not specified"
    fwks = ", ".join(ts.get("frameworks",     [])) or "not specified"
    infr = ", ".join(ts.get("infrastructure", [])) or "not specified"
    fend = ", ".join(ts.get("frontend",       [])) or "not specified"

    domains_text = "\n".join(f"- {d}" for d in profile.get("client_domains", [])) or "- not specified"

    projects_text = ""
    for p in profile.get("projects", []):
        if p.get("name"):
            tech = ", ".join(p.get("tech", [])) or "various"
            desc = p.get("description", "")
            projects_text += f"- {p['name']}: {desc} (stack: {tech})\n"
    projects_text = projects_text.strip() or "- No active projects specified"

    interests_text  = "\n".join(f"- {i}" for i in profile.get("interests",  [])) or "- not specified"
    exclusions_text = "\n".join(f"- {e}" for e in profile.get("exclusions", [])) or "- not specified"
    min_score       = profile.get("min_score", 7)

    return f"""
You are scoring news articles for a {role} at a {company_type} operating in {market}.

Tech stack:
- LLM providers: {llms}
- Agent / LLM frameworks: {fwks}
- Cloud & infrastructure: {infr}
- Frontend & APIs: {fend}

Client domains:
{domains_text}

Active projects:
{projects_text}

Topics to PRIORITISE (score high):
{interests_text}

Topics to EXCLUDE (score low):
{exclusions_text}

Scoring philosophy: Be STRICT. The relevance bar is {min_score}/10.
- Score {min_score}–10: Directly actionable for their work — worth reading today
- Score {min_score - 2}–{min_score - 1}: Tangentially relevant — interesting but not urgent
- Score 1–{min_score - 3}: Noise — irrelevant to this person's actual work

BONUS — push score to 9–10 for:
- Production deployments in their client domains with measured outcomes (ROI, accuracy %)
- Architecture patterns they can reuse: RAG pipelines, agent orchestration, evaluation setups
- Client-ready business cases: risk reduction, cost savings, compliance angles
- Step-by-step tutorials with working code for their specific tech stack
- EU/DACH regulatory guidance with concrete compliance checklists
- Model or framework comparisons that directly affect their stack choices
""".strip()


# ── LLM initialisation ────────────────────────────────────────────────────────

def get_llm() -> AzureChatOpenAI:
    """Initialise AzureChatOpenAI from environment variables."""
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        temperature=0,
    )


# ── Fetching ──────────────────────────────────────────────────────────────────

# Strip characters that are illegal in XML 1.0 (control chars except tab/LF/CR)
_INVALID_XML_RE = re.compile(
    r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]"
)

def _clean_xml(raw: bytes) -> str:
    """Decode bytes and remove characters illegal in XML 1.0 before feedparser sees them."""
    text = raw.decode("utf-8", errors="replace")
    return _INVALID_XML_RE.sub("", text)


def _extract_snippet(entry: dict) -> str:
    """Pull the best available text snippet from a feedparser entry (max 600 chars)."""
    for field in ("summary", "description", "content"):
        value = entry.get(field)
        if isinstance(value, list) and value:
            value = value[0].get("value", "")
        if value:
            # Strip any HTML tags for a clean plaintext snippet
            cleaned = re.sub(r"<[^>]+>", " ", str(value))
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            return cleaned[:600]
    return ""


def fetch_rss(source_name: str, url: str, max_entries: int = 5) -> list[dict]:
    """Fetch an RSS feed via requests, clean illegal XML chars, parse with feedparser.
    Returns up to max_entries articles including a text snippet for LLM context."""
    headers = {"User-Agent": "GenAIRadar/1.0 (personal digest bot)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(_clean_xml(resp.content))
        if not feed.entries:
            raise ValueError("feed returned 0 entries after cleaning")
        articles = []
        for entry in feed.entries[:max_entries]:
            title   = entry.get("title", "").strip()
            link    = entry.get("link", "").strip()
            snippet = _extract_snippet(entry)
            if title and link:
                articles.append({
                    "title":   title,
                    "url":     link,
                    "source":  source_name,
                    "snippet": snippet,
                })
        return articles
    except Exception as e:
        print(f"  [WARNING] {source_name}: {e}")
        return []


def fetch_reddit(subreddit: str, max_posts: int = 5) -> list[dict]:
    """Fetch top posts of the day from a subreddit via the public JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={max_posts}"
    headers = {"User-Agent": "GenAIRadar/1.0 (personal digest bot)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        posts = []
        for child in resp.json()["data"]["children"][:max_posts]:
            p       = child["data"]
            title   = p.get("title", "").strip()
            permalink = p.get("permalink", "")
            # selftext is the post body for text posts; empty for link posts
            snippet = p.get("selftext", "")[:400].strip()
            if title and permalink:
                posts.append({
                    "title":   title,
                    "url":     f"https://www.reddit.com{permalink}",
                    "source":  f"r/{subreddit}",
                    "snippet": snippet,
                })
        return posts
    except Exception as e:
        print(f"  [WARNING] r/{subreddit}: {e}")
        return []


# ── Deduplication ─────────────────────────────────────────────────────────────

def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by URL, preserving order of first occurrence."""
    seen: set[str] = set()
    unique = []
    for article in articles:
        if article["url"] not in seen:
            seen.add(article["url"])
            unique.append(article)
    return unique


# ── Scoring ───────────────────────────────────────────────────────────────────

_JSON_SCHEMA = """\
Respond with a single JSON object — no markdown, no code fences, just raw JSON.
Required fields:
  "relevance_score": integer 1-10
  "reason": one sentence — why this matters to the consultant specifically
  "summary": 2-3 sentences — consultant-focused summary, skip generic context
  "actionable_insights": array of 2-3 strings — concrete things to act on today
  "category": one of: models | tools | implementation | industry | regulation | tutorial
  "domain": one of: general | finance | insurance | hr | data-science
  "worth_reading": boolean — true if score >= 7 and directly actionable
"""

def score_article(llm, article: dict, profile_text: str) -> "Article | None":
    """Score one article using a plain-JSON prompt — no function calling.

    Asks the LLM to return raw JSON, then parses and validates it into an Article.
    This is compatible with all GPT-4 versions and API versions.
    """
    snippet_block = f"Excerpt: {article['snippet'][:400]}\n" if article.get("snippet") else ""
    prompt = (
        f"{profile_text}\n\n"
        f"Article to score:\n"
        f"Title:  {article['title']}\n"
        f"Source: {article['source']}\n"
        f"{snippet_block}\n"
        f"{_JSON_SCHEMA}"
    )
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        # Strip markdown code fences if the model added them anyway
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        return Article(
            title               = article["title"],
            url                 = article["url"],
            source              = article["source"],
            relevance_score     = int(data["relevance_score"]),
            reason              = str(data.get("reason", "")),
            summary             = str(data.get("summary", "")),
            actionable_insights = list(data.get("actionable_insights", [])),
            category            = data.get("category", "industry"),
            domain              = data.get("domain", "general"),
            worth_reading       = bool(data.get("worth_reading", False)),
        )
    except Exception as e:
        print(f"  [ERROR] '{article['title'][:60]}': {type(e).__name__}: {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== GenAI Radar — Daily Fetch ===\n")

    failed_sources: list[str] = []
    all_raw: list[dict] = []

    # Fetch all RSS feeds
    print("Fetching RSS feeds...")
    for name, url in RSS_SOURCES.items():
        articles = fetch_rss(name, url)
        if not articles:
            failed_sources.append(name)
        else:
            all_raw.extend(articles)
            print(f"  {name}: {len(articles)} articles")

    # Fetch Reddit posts
    print("\nFetching Reddit posts...")
    for sub in REDDIT_SUBS:
        posts = fetch_reddit(sub)
        if not posts:
            failed_sources.append(f"r/{sub}")
        else:
            all_raw.extend(posts)
            print(f"  r/{sub}: {len(posts)} posts")

    raw_count = len(all_raw)
    print(f"\nRaw articles fetched:  {raw_count}")

    # Deduplicate by URL
    unique_articles = deduplicate(all_raw)
    dedup_count = len(unique_articles)
    print(f"After deduplication:   {dedup_count}")

    # Load profile — drives the scoring prompt and minimum score threshold
    profile    = load_profile()
    min_score  = profile.get("min_score", 7) if profile else 7
    profile_text = build_profile_prompt(profile) if profile else PROFILE
    if profile:
        print(f"\nUsing saved profile: {profile.get('role', 'unknown role')} "
              f"(min score: {min_score})")
    else:
        print("\nNo profile.json found — using built-in default profile.")

    # Score each article — plain JSON prompt, no function calling
    print(f"Scoring {dedup_count} articles with Azure OpenAI...")
    llm = get_llm()

    # Collect all scored results, not just passing ones — needed for the safety net
    all_scored: list[Article] = []
    passed: list[Article] = []
    for i, article in enumerate(unique_articles, 1):
        print(f"  [{i:>3}/{dedup_count}] {article['title'][:65]}...")
        result = score_article(llm, article, profile_text)
        if result:
            all_scored.append(result)
            # Filter on score alone — worth_reading can be overly conservative
            if result.relevance_score >= min_score:
                passed.append(result)
        time.sleep(0.3)  # gentle rate-limit buffer

    # Safety net: if nothing passed, keep the top 3 scored articles regardless
    MIN_ARTICLES = 3
    if len(passed) < MIN_ARTICLES and all_scored:
        all_scored.sort(key=lambda a: a.relevance_score, reverse=True)
        fallback = [a for a in all_scored if a not in passed]
        needed   = MIN_ARTICLES - len(passed)
        passed.extend(fallback[:needed])
        print(f"  [INFO] Safety net: added {min(needed, len(fallback))} article(s) "
              f"below threshold to reach minimum of {MIN_ARTICLES}.")

    # Sort best-first
    passed.sort(key=lambda a: a.relevance_score, reverse=True)

    # Persist digest — include raw/dedup counts for the FOMO stats in the UI
    os.makedirs("data", exist_ok=True)
    digest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(passed),
        "raw_count":     raw_count,
        "dedup_count":   dedup_count,
        "articles":      [a.model_dump() for a in passed],
    }
    with open("data/digest.json", "w", encoding="utf-8") as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)

    # Summary
    print("\n=== Summary ===")
    print(f"  Raw articles fetched:     {raw_count}")
    print(f"  After deduplication:      {dedup_count}")
    print(f"  Passed filter (score≥{min_score}): {len(passed)}")
    if failed_sources:
        print(f"  Failed sources ({len(failed_sources)}):      {', '.join(failed_sources)}")
    else:
        print("  Failed sources:           none")
    print(f"\nDigest saved → data/digest.json")


if __name__ == "__main__":
    main()
