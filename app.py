import json
import os
import subprocess
import requests
from datetime import datetime, timezone

import streamlit as st

DIGEST_PATH = "data/digest.json"

# ── Constants ─────────────────────────────────────────────────────────────────

ALL_CATEGORIES = ["models", "tools", "implementation", "industry", "regulation", "tutorial"]
ALL_DOMAINS    = ["general", "finance", "insurance", "hr", "data-science"]

DOMAIN_COLORS = {
    "general":      "blue",
    "finance":      "green",
    "insurance":    "violet",
    "hr":           "orange",
    "data-science": "red",
}
DOMAIN_LABELS = {
    "general":      "General",
    "finance":      "Finance",
    "insurance":    "Insurance",
    "hr":           "HR",
    "data-science": "Data Science",
}
CATEGORY_ICONS = {
    "models":         "🚀",
    "tools":          "🔧",
    "implementation": "⚙️",
    "industry":       "🏢",
    "regulation":     "⚖️",
    "tutorial":       "📚",
}

TOTAL_SOURCES = 23

# ── Profile form option lists ─────────────────────────────────────────────────

TECH_LLM_OPTIONS = [
    "Azure OpenAI", "OpenAI", "Anthropic Claude", "Google Gemini",
    "Mistral", "Meta Llama", "Cohere", "AWS Bedrock",
]
TECH_FRAMEWORK_OPTIONS = [
    "LangGraph", "LangChain", "LlamaIndex", "Semantic Kernel",
    "AutoGen", "CrewAI", "Haystack", "DSPy", "Vercel AI SDK",
]
TECH_INFRA_OPTIONS = [
    "Azure", "Azure Container Apps", "AWS", "GCP",
    "On-premise", "Kubernetes", "Docker",
]
TECH_FRONTEND_OPTIONS = [
    "Streamlit", "React", "Vue", "Angular", "Gradio", "FastAPI", "Flask",
]
DOMAIN_OPTIONS = [
    "Finance & Banking", "Insurance", "HR & Talent Management",
    "Data Science & Analytics", "Healthcare", "Retail",
    "Manufacturing", "Legal", "Public Sector",
]
MARKET_OPTIONS = ["Germany / DACH", "EU", "UK", "US", "Global"]
COMPANY_TYPE_OPTIONS = [
    "IT Consultancy", "Enterprise (internal)", "Startup / Scale-up", "Agency", "Research / Academia",
]
PROJECT_TECH_OPTIONS = [
    "Azure OpenAI", "LangGraph", "LangChain", "LlamaIndex", "Streamlit",
    "FastAPI", "Flask", "Azure Container Apps", "MS365 / SharePoint",
    "Azure AI Search", "Pinecone", "pgvector", "PostgreSQL",
    "Python", "React", "Docker", "Kubernetes",
]
INTEREST_OPTIONS = [
    "Model releases & capability updates (GPT, Claude, Gemini)",
    "LangGraph & agentic framework updates",
    "RAG patterns, chunking & retrieval",
    "Azure AI & Microsoft AI products",
    "EU AI Act & DORA compliance",
    "Production use cases & implementation patterns",
    "InsurTech AI adoption",
    "FinTech AI adoption",
    "AI in HR & people analytics",
    "LLM evaluation & observability",
    "Practical tutorials with working code",
    "Enterprise AI architecture decisions",
    "Vector databases & embeddings",
    "Multi-agent orchestration",
    "Cost optimisation for LLM workloads",
    "Prompt engineering & fine-tuning",
]
EXCLUSION_OPTIONS = [
    "Academic research (no practical application)",
    "Consumer AI apps (photo filters, gaming, entertainment)",
    "Crypto, blockchain, Web3",
    "US-only regulatory news (no EU relevance)",
    "Generic 'AI will change everything' opinion pieces",
    "Vendor marketing without technical substance",
    "Hardware & chip news",
    "AI art & creative tools",
]

DEFAULT_PROFILE: dict = {
    "role":         "GenAI Implementation Consultant",
    "company_type": "IT Consultancy",
    "market":       ["Germany / DACH", "EU"],
    "tech_stack": {
        "llm_providers": ["Azure OpenAI"],
        "frameworks":    ["LangGraph", "LangChain"],
        "infrastructure": ["Azure", "Azure Container Apps"],
        "frontend":      ["Streamlit"],
    },
    "client_domains": [
        "Finance & Banking", "Insurance",
        "HR & Talent Management", "Data Science & Analytics",
    ],
    "projects": [
        {"name": "", "description": "", "tech": []},
        {"name": "", "description": "", "tech": []},
        {"name": "", "description": "", "tech": []},
    ],
    "interests": [
        "Model releases & capability updates (GPT, Claude, Gemini)",
        "LangGraph & agentic framework updates",
        "RAG patterns, chunking & retrieval",
        "Azure AI & Microsoft AI products",
        "EU AI Act & DORA compliance",
        "Production use cases & implementation patterns",
        "InsurTech AI adoption",
        "FinTech AI adoption",
        "AI in HR & people analytics",
        "LLM evaluation & observability",
        "Practical tutorials with working code",
    ],
    "exclusions": [
        "Academic research (no practical application)",
        "Consumer AI apps (photo filters, gaming, entertainment)",
        "Crypto, blockchain, Web3",
        "US-only regulatory news (no EU relevance)",
        "Generic 'AI will change everything' opinion pieces",
    ],
    "min_score": 7,
}


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_users() -> dict[str, str]:
    """Load username→password map from Streamlit secrets [users] section.
    Falls back to single APP_PASSWORD under username 'user' for backward compat."""
    try:
        users = dict(st.secrets.get("users", {}))
        if users:
            return users
    except Exception:
        pass
    # Fallback: single-user mode via APP_PASSWORD env var
    pwd = os.environ.get("APP_PASSWORD", "")
    return {"user": pwd} if pwd else {}


def check_login() -> bool:
    """Show login form, return True once the user is authenticated.
    Stores username in st.session_state.username on success."""
    if st.session_state.get("username"):
        return True

    users = get_users()
    if not users:
        # No auth configured — open access (local dev)
        st.session_state.username = "local"
        return True

    st.set_page_config(page_title="GenAI Radar", layout="centered", page_icon="📡")
    st.title("GenAI Radar")
    st.markdown("---")

    multi_user = len(users) > 1 or "user" not in users

    if multi_user:
        username_input = st.text_input("Username")
    else:
        username_input = "user"

    password_input = st.text_input("Password", type="password")

    if st.button("Sign in", use_container_width=True):
        expected = users.get(username_input, "")
        if expected and password_input == expected:
            st.session_state.username = username_input
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    return False


# ── Supabase client ───────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase():
    """Return a cached Supabase client, or None if not configured."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        st.warning(f"Supabase init failed: {e} — using local storage fallback.")
        return None


# ── Data layer — favorites ────────────────────────────────────────────────────

def load_favorites(username: str) -> dict:
    """Load favorites for a user. Uses Supabase if configured, else local JSON."""
    db = get_supabase()
    if db:
        try:
            rows = db.table("favorites").select("*").eq("username", username).execute().data
            return {
                "favorites": [
                    {
                        "article":  row["article"],
                        "saved_at": row["saved_at"],
                        "comment":  row.get("comment", ""),
                    }
                    for row in rows
                ]
            }
        except Exception as e:
            st.warning(f"Could not load favorites from database: {e}")
            return {"favorites": []}

    # Local fallback — per-user file
    path = f"data/favorites_{username}.json"
    if not os.path.exists(path):
        return {"favorites": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_favorite(username: str, article: dict) -> None:
    """Save an article to a user's favorites."""
    db = get_supabase()
    if db:
        try:
            db.table("favorites").upsert({
                "username": username,
                "url":      article["url"],
                "article":  article,
                "comment":  "",
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="username,url").execute()
        except Exception as e:
            st.error(f"Could not save favorite: {e}")
        return

    # Local fallback
    favs = load_favorites(username)
    favs["favorites"].append({
        "article":  article,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "comment":  "",
    })
    _save_favorites_local(username, favs)


def remove_favorite(username: str, url: str) -> None:
    """Remove an article from a user's favorites."""
    db = get_supabase()
    if db:
        try:
            db.table("favorites").delete().eq("username", username).eq("url", url).execute()
        except Exception as e:
            st.error(f"Could not remove favorite: {e}")
        return

    favs = load_favorites(username)
    favs["favorites"] = [f for f in favs["favorites"] if f["article"]["url"] != url]
    _save_favorites_local(username, favs)


def update_comment(username: str, url: str, comment: str) -> None:
    """Update the note for a saved article."""
    db = get_supabase()
    if db:
        try:
            db.table("favorites").update({"comment": comment}).eq("username", username).eq("url", url).execute()
        except Exception as e:
            st.error(f"Could not save note: {e}")
        return

    favs = load_favorites(username)
    for fav in favs["favorites"]:
        if fav["article"]["url"] == url:
            fav["comment"] = comment
            break
    _save_favorites_local(username, favs)


def _save_favorites_local(username: str, data: dict) -> None:
    """Write favorites to a per-user local JSON file."""
    os.makedirs("data", exist_ok=True)
    with open(f"data/favorites_{username}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def favorited_urls(favorites: dict) -> set[str]:
    """Return the set of article URLs saved by this user."""
    return {fav["article"]["url"] for fav in favorites.get("favorites", [])}


# ── Data layer — profile ──────────────────────────────────────────────────────

def load_profile(username: str) -> dict:
    """Load profile for a user. Uses Supabase if configured, else local JSON."""
    db = get_supabase()
    if db:
        try:
            rows = db.table("user_profiles").select("profile").eq("username", username).execute().data
            if rows:
                return rows[0]["profile"]
        except Exception as e:
            st.warning(f"Could not load profile from database: {e}")
        return DEFAULT_PROFILE.copy()

    path = f"data/profile_{username}.json"
    if not os.path.exists(path):
        # Also check old single-user path for migration
        if os.path.exists("data/profile.json"):
            with open("data/profile.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return DEFAULT_PROFILE.copy()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(username: str, data: dict) -> None:
    """Save profile for a user."""
    db = get_supabase()
    if db:
        try:
            db.table("user_profiles").upsert({
                "username":   username,
                "profile":    data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="username").execute()
        except Exception as e:
            st.error(f"Could not save profile: {e}")
        return

    os.makedirs("data", exist_ok=True)
    with open(f"data/profile_{username}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Digest ────────────────────────────────────────────────────────────────────

def load_digest() -> dict | None:
    """Load the shared daily digest from disk."""
    if not os.path.exists(DIGEST_PATH):
        return None
    with open(DIGEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def format_timestamp(iso_str: str) -> tuple[str, str]:
    """Parse an ISO-8601 string and return (date_str, time_str)."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M UTC")


# ── Rendering helpers ─────────────────────────────────────────────────────────

def domain_badge(domain: str) -> str:
    color = DOMAIN_COLORS.get(domain, "blue")
    label = DOMAIN_LABELS.get(domain, domain)
    return f":{color}-badge[{label}]"


def render_article_card(article: dict, saved_urls: set[str], username: str, key_prefix: str = "") -> None:
    """Render one article card with save toggle, summary expander, and meta row."""
    with st.container():
        title    = article["title"]
        url      = article["url"]
        source   = article["source"]
        score    = article["relevance_score"]
        reason   = article.get("reason", "")
        summary  = article.get("summary", "")
        insights = article.get("actionable_insights", [])
        category = article["category"]
        domain   = article["domain"]
        is_saved = url in saved_urls

        icon  = CATEGORY_ICONS.get(category, "")
        badge = domain_badge(domain)

        title_col, btn_col = st.columns([11, 1])
        with title_col:
            st.markdown(f"### [{title}]({url})")
        with btn_col:
            star = "⭐" if is_saved else "☆"
            help_text = "Unsave" if is_saved else "Save"
            if st.button(star, key=f"{key_prefix}{url}", help=help_text, use_container_width=True):
                if is_saved:
                    remove_favorite(username, url)
                else:
                    add_favorite(username, article)
                st.rerun()

        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"**{source}** &nbsp; {badge}")
        with c2:
            st.markdown(f"**{score}/10**")
        with c3:
            st.markdown(f"{icon} `{category}`")

        st.caption(reason)

        if summary or insights:
            with st.expander("AI Summary & Insights"):
                if summary:
                    st.markdown(summary)
                if insights:
                    st.markdown("**Actionable insights**")
                    for insight in insights:
                        st.markdown(f"- {insight}")

        st.divider()


# ── GitHub Actions trigger ────────────────────────────────────────────────────

def trigger_github_action() -> tuple[bool, str]:
    """Dispatch the daily_fetch workflow via the GitHub API."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPO", "")

    if token and repo:
        url  = f"https://api.github.com/repos/{repo}/actions/workflows/daily_fetch.yml/dispatches"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"ref": "main"},
            timeout=15,
        )
        if resp.status_code == 204:
            return True, "Workflow triggered. New articles will appear in ~3 minutes."
        return False, f"GitHub API returned {resp.status_code}: {resp.text}"

    import sys
    repo_root = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "fetch.py")],
        capture_output=True, text=True, cwd=repo_root,
    )
    return result.returncode == 0, result.stdout + result.stderr


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_radar(digest: dict, username: str) -> None:
    """Main Radar page — FOMO stats, filters, article cards."""
    articles     = digest.get("articles", [])
    passed_count = digest.get("article_count", len(articles))
    raw_count    = digest.get("raw_count")
    dedup_count  = digest.get("dedup_count")
    filtered_out = (dedup_count - passed_count) if dedup_count is not None else None
    pct_str      = f"{int(100 * passed_count / dedup_count)}%" if dedup_count else "—"
    date_str, time_str = format_timestamp(digest["generated_at"])

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Scanned today",  raw_count if raw_count is not None else "—")
    with m2:
        st.metric("Made the cut",   passed_count)
    with m3:
        st.metric("Filtered out",   filtered_out if filtered_out is not None else "—")
    with m4:
        st.metric("Last updated",   f"{date_str} {time_str}")

    if raw_count is not None:
        st.caption(
            f"We read **{raw_count} articles** across **{TOTAL_SOURCES} sources** so you "
            f"didn't have to. Only the top **{pct_str}** passed the relevance bar."
        )
    else:
        st.caption("Hit **Refresh now** to see full scan statistics.")
    st.markdown("---")

    cat_filter    = st.session_state.get("filter_cats")    or ALL_CATEGORIES
    domain_filter = st.session_state.get("filter_domains") or ALL_DOMAINS

    filtered = [
        a for a in articles
        if a["category"] in cat_filter and a["domain"] in domain_filter
    ]
    if st.session_state.get("filter_sort", "Relevance") == "Relevance":
        filtered.sort(key=lambda a: a["relevance_score"], reverse=True)
    else:
        filtered.sort(key=lambda a: (a["category"], -a["relevance_score"]))

    favorites  = load_favorites(username)
    saved_urls = favorited_urls(favorites)

    count_word = "article" if len(filtered) == 1 else "articles"
    st.markdown(f"**Showing {len(filtered)} {count_word}**")

    if not filtered:
        st.warning("No articles match the current filters. Try widening your selection in the sidebar.")
        return

    for article in filtered:
        render_article_card(article, saved_urls, username, key_prefix="radar_")


def page_saved(username: str) -> None:
    """Saved articles page — per-user favorites with notes."""
    st.title("Saved Articles")
    favorites = load_favorites(username)
    items     = favorites.get("favorites", [])

    if not items:
        st.info("No saved articles yet.\n\nGo to **Radar** and click ☆ on any article to save it here.")
        return

    count_word = "article" if len(items) == 1 else "articles"
    st.markdown(f"**{len(items)} saved {count_word}**")
    st.markdown("---")

    for i, fav in enumerate(items):
        article  = fav["article"]
        saved_at = fav.get("saved_at", "")
        comment  = fav.get("comment", "")
        url      = article["url"]

        with st.container():
            title    = article["title"]
            source   = article["source"]
            score    = article["relevance_score"]
            category = article["category"]
            domain   = article["domain"]
            summary  = article.get("summary", "")
            insights = article.get("actionable_insights", [])

            badge = domain_badge(domain)
            icon  = CATEGORY_ICONS.get(category, "")

            title_col, rm_col = st.columns([11, 1])
            with title_col:
                st.markdown(f"### [{title}]({url})")
            with rm_col:
                if st.button("🗑️", key=f"rm_{url}_{i}", help="Remove", use_container_width=True):
                    remove_favorite(username, url)
                    st.rerun()

            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f"**{source}** &nbsp; {badge}")
            with c2:
                st.markdown(f"**{score}/10**")
            with c3:
                st.markdown(f"{icon} `{category}`")

            if saved_at:
                try:
                    dt = datetime.fromisoformat(saved_at.replace("Z", "+00:00"))
                    st.caption(f"Saved {dt.strftime('%Y-%m-%d %H:%M UTC')}")
                except Exception:
                    pass

            if summary or insights:
                with st.expander("AI Summary & Insights"):
                    if summary:
                        st.markdown(summary)
                    if insights:
                        st.markdown("**Actionable insights**")
                        for insight in insights:
                            st.markdown(f"- {insight}")

            st.markdown("**My notes**")
            new_comment = st.text_area(
                "note",
                value=comment,
                key=f"note_{url}_{i}",
                label_visibility="collapsed",
                placeholder="Client context, follow-up ideas, things to share…",
                height=90,
            )
            save_col, _ = st.columns([1, 6])
            with save_col:
                if st.button("Save note", key=f"save_note_{url}_{i}"):
                    update_comment(username, url, new_comment)
                    st.toast("Note saved!", icon="✅")

            st.divider()


def page_profile(username: str) -> None:
    """Profile page — per-user settings that shape AI scoring."""
    st.title("Profile")
    st.markdown("Your profile shapes how articles are scored and what insights the AI highlights.")
    st.info("Changes take effect after the next **Refresh now**.", icon="ℹ️")
    st.markdown("---")

    profile = load_profile(username)
    ts = profile.get("tech_stack", {})

    def _safe_default(value: list, options: list) -> list:
        return [v for v in value if v in options]

    with st.form("profile_form"):
        st.subheader("About You")
        role = st.text_input("Your role", value=profile.get("role", ""))
        ab_col1, ab_col2 = st.columns(2)
        with ab_col1:
            ct_val = profile.get("company_type", COMPANY_TYPE_OPTIONS[0])
            company_type = st.selectbox(
                "Company type",
                options=COMPANY_TYPE_OPTIONS,
                index=COMPANY_TYPE_OPTIONS.index(ct_val) if ct_val in COMPANY_TYPE_OPTIONS else 0,
            )
        with ab_col2:
            market = st.multiselect(
                "Primary market",
                options=MARKET_OPTIONS,
                default=_safe_default(profile.get("market", []), MARKET_OPTIONS),
            )

        st.markdown("---")
        st.subheader("Tech Stack")
        ts_col1, ts_col2 = st.columns(2)
        with ts_col1:
            llm_providers = st.multiselect(
                "LLM providers",
                options=TECH_LLM_OPTIONS,
                default=_safe_default(ts.get("llm_providers", []), TECH_LLM_OPTIONS),
            )
            infra = st.multiselect(
                "Cloud & infrastructure",
                options=TECH_INFRA_OPTIONS,
                default=_safe_default(ts.get("infrastructure", []), TECH_INFRA_OPTIONS),
            )
        with ts_col2:
            frameworks = st.multiselect(
                "Agent / LLM frameworks",
                options=TECH_FRAMEWORK_OPTIONS,
                default=_safe_default(ts.get("frameworks", []), TECH_FRAMEWORK_OPTIONS),
            )
            frontend = st.multiselect(
                "Frontend & APIs",
                options=TECH_FRONTEND_OPTIONS,
                default=_safe_default(ts.get("frontend", []), TECH_FRONTEND_OPTIONS),
            )

        st.markdown("---")
        st.subheader("Client Domains")
        client_domains = st.multiselect(
            "Domains you serve",
            options=DOMAIN_OPTIONS,
            default=_safe_default(profile.get("client_domains", []), DOMAIN_OPTIONS),
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.subheader("Active Projects")
        st.caption("Up to 3 projects. These help the AI tailor insights to what you're actually building.")
        raw_projects = profile.get("projects", [{}, {}, {}])
        while len(raw_projects) < 3:
            raw_projects.append({})

        saved_projects = []
        for idx in range(3):
            p = raw_projects[idx]
            with st.expander(f"Project {idx + 1}", expanded=bool(p.get("name"))):
                p_name = st.text_input("Name", value=p.get("name", ""), key=f"p_name_{idx}", placeholder="e.g. A-MATCH")
                p_desc = st.text_input("One-line description", value=p.get("description", ""), key=f"p_desc_{idx}", placeholder="What does it do and for whom?")
                p_tech = st.multiselect("Key technologies", options=PROJECT_TECH_OPTIONS, default=_safe_default(p.get("tech", []), PROJECT_TECH_OPTIONS), key=f"p_tech_{idx}")
            saved_projects.append({"name": p_name, "description": p_desc, "tech": p_tech})

        st.markdown("---")
        st.subheader("Topics")
        tp_col1, tp_col2 = st.columns(2)
        with tp_col1:
            st.markdown("**Prioritise**")
            interests = st.multiselect("prioritise", options=INTEREST_OPTIONS, default=_safe_default(profile.get("interests", []), INTEREST_OPTIONS), label_visibility="collapsed")
        with tp_col2:
            st.markdown("**Exclude**")
            exclusions = st.multiselect("exclude", options=EXCLUSION_OPTIONS, default=_safe_default(profile.get("exclusions", []), EXCLUSION_OPTIONS), label_visibility="collapsed")

        st.markdown("---")
        st.subheader("Filtering")
        min_score = st.slider("Minimum relevance score", min_value=5, max_value=9, value=profile.get("min_score", 7))

        submitted = st.form_submit_button("Save Profile", use_container_width=True, type="primary")

    if submitted:
        save_profile(username, {
            "role":         role,
            "company_type": company_type,
            "market":       market,
            "tech_stack": {
                "llm_providers": llm_providers,
                "frameworks":    frameworks,
                "infrastructure":infra,
                "frontend":      frontend,
            },
            "client_domains": client_domains,
            "projects":  [p for p in saved_projects if p["name"]],
            "interests": interests,
            "exclusions":exclusions,
            "min_score": min_score,
        })
        st.success("Profile saved.")
        st.info("Click **Refresh now** in the sidebar to apply your updated profile to the next digest.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not check_login():
        st.stop()

    st.set_page_config(page_title="GenAI Radar", layout="wide", page_icon="📡")

    username = st.session_state.username

    defaults: dict = {
        "page":           "radar",
        "filter_cats":    ALL_CATEGORIES.copy(),
        "filter_domains": ALL_DOMAINS.copy(),
        "filter_sort":    "Relevance",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    digest    = load_digest()
    favorites = load_favorites(username)
    fav_count = len(favorites.get("favorites", []))

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("GenAI Radar")
        st.caption(f"Signed in as **{username}**")
        st.markdown("---")

        # Navigation
        nav_col1, nav_col2, nav_col3 = st.columns(3)
        with nav_col1:
            if st.button("Radar", use_container_width=True, disabled=(st.session_state.page == "radar")):
                st.session_state.page = "radar"
                st.rerun()
        with nav_col2:
            saved_label = f"Saved ({fav_count})" if fav_count else "Saved"
            if st.button(saved_label, use_container_width=True, disabled=(st.session_state.page == "saved")):
                st.session_state.page = "saved"
                st.rerun()
        with nav_col3:
            if st.button("Profile", use_container_width=True, disabled=(st.session_state.page == "profile")):
                st.session_state.page = "profile"
                st.rerun()

        st.markdown("---")

        # Filters
        if st.session_state.page == "radar" and digest is not None:
            st.markdown("**Filters**")
            st.multiselect("Category", options=ALL_CATEGORIES, key="filter_cats", format_func=lambda c: f"{CATEGORY_ICONS.get(c, '')} {c}")
            st.multiselect("Domain",   options=ALL_DOMAINS,    key="filter_domains", format_func=lambda d: DOMAIN_LABELS.get(d, d))
            st.radio("Sort by", options=["Relevance", "Category"], key="filter_sort")
            st.markdown("---")

        # Refresh
        if st.button("Refresh now", use_container_width=True):
            token = os.environ.get("GITHUB_TOKEN", "")
            repo  = os.environ.get("GITHUB_REPO", "")
            if not token or not repo:
                st.session_state["refresh_msg"] = ("warning", "GITHUB_TOKEN and GITHUB_REPO not set in Streamlit secrets.")
            else:
                with st.spinner("Triggering GitHub Actions workflow…"):
                    success, message = trigger_github_action()
                st.session_state["refresh_msg"] = ("ok" if success else "error", message)

        msg = st.session_state.get("refresh_msg")
        if msg:
            kind, text = msg
            {"ok": st.success, "warning": st.warning, "error": st.error}[kind](text)

        if digest:
            date_str, time_str = format_timestamp(digest["generated_at"])
            st.caption(f"Last fetch: {date_str} · {time_str}")
        else:
            st.caption("No digest yet")
        st.caption(f"Monitoring {TOTAL_SOURCES} sources")

        st.markdown("---")
        if st.button("Sign out", use_container_width=True):
            for k in ["username", "page", "filter_cats", "filter_domains", "filter_sort", "refresh_msg"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Route ─────────────────────────────────────────────────────────────────
    if st.session_state.page == "saved":
        page_saved(username)
        return

    if st.session_state.page == "profile":
        page_profile(username)
        return

    st.title("📡 GenAI Radar")
    st.markdown("*Your daily AI news digest — filtered for what actually matters to your work.*")

    if digest is None:
        st.info(
            "**No digest found yet.** To get started:\n\n"
            "1. Copy `.env.example` → `.env` and fill in your Azure OpenAI credentials.\n"
            "2. Run `python fetch.py` locally, **or**\n"
            "3. Go to your GitHub repo → **Actions** tab → **Run workflow**."
        )
        return

    page_radar(digest, username)


if __name__ == "__main__":
    main()
