import json
import os
import subprocess
from datetime import datetime

import streamlit as st

DIGEST_PATH    = "data/digest.json"
FAVORITES_PATH = "data/favorites.json"
PROFILE_PATH   = "data/profile.json"

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

TOTAL_SOURCES = 23  # 20 RSS + 3 Reddit

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

# Pre-filled defaults so first-time users can just review + submit
DEFAULT_PROFILE: dict = {
    "role":         "GenAI Implementation Consultant",
    "company_type": "IT Consultancy",
    "market":       ["Germany / DACH", "EU"],
    "tech_stack": {
        "llm_providers": ["Azure OpenAI"],
        "frameworks":    ["LangGraph", "LangChain"],
        "infrastructure":["Azure", "Azure Container Apps"],
        "frontend":      ["Streamlit"],
    },
    "client_domains": [
        "Finance & Banking", "Insurance",
        "HR & Talent Management", "Data Science & Analytics",
    ],
    "projects": [
        {
            "name": "A-MATCH",
            "description": "Internal mobility platform — AI-powered talent matching for HR",
            "tech": ["LangGraph", "Azure OpenAI", "Streamlit"],
        },
        {
            "name": "Text2SQL Data Analyst",
            "description": "Natural language to SQL agent for business data analysis",
            "tech": ["LangChain", "Azure OpenAI", "Streamlit"],
        },
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


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_digest() -> dict | None:
    """Load digest.json; return None if it doesn't exist yet."""
    if not os.path.exists(DIGEST_PATH):
        return None
    with open(DIGEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_favorites() -> dict:
    """Load favorites.json; return an empty structure if not found."""
    if not os.path.exists(FAVORITES_PATH):
        return {"favorites": []}
    with open(FAVORITES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_favorites(data: dict) -> None:
    """Persist favorites to disk."""
    os.makedirs("data", exist_ok=True)
    with open(FAVORITES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def favorited_urls(favorites: dict) -> set[str]:
    """Return the set of URLs currently in the favorites list."""
    return {fav["article"]["url"] for fav in favorites.get("favorites", [])}


def add_favorite(article: dict, favorites: dict) -> dict:
    """Add an article to favorites with an empty comment."""
    favorites["favorites"].append({
        "article":  article,
        "saved_at": datetime.utcnow().isoformat(),
        "comment":  "",
    })
    return favorites


def remove_favorite(url: str, favorites: dict) -> dict:
    """Remove a favorite by URL."""
    favorites["favorites"] = [
        f for f in favorites["favorites"] if f["article"]["url"] != url
    ]
    return favorites


def load_profile() -> dict:
    """Load profile.json; return DEFAULT_PROFILE if not found."""
    if not os.path.exists(PROFILE_PATH):
        return DEFAULT_PROFILE.copy()
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(data: dict) -> None:
    """Persist profile to disk."""
    os.makedirs("data", exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_comment(url: str, comment: str, favorites: dict) -> dict:
    """Update the comment for a saved article."""
    for fav in favorites["favorites"]:
        if fav["article"]["url"] == url:
            fav["comment"] = comment
            break
    return favorites


def format_timestamp(iso_str: str) -> tuple[str, str]:
    """Parse an ISO-8601 string and return (date_str, time_str)."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M UTC")


# ── Rendering helpers ─────────────────────────────────────────────────────────

def domain_badge(domain: str) -> str:
    """Return a Streamlit colored-badge markdown string for a domain."""
    color = DOMAIN_COLORS.get(domain, "blue")
    label = DOMAIN_LABELS.get(domain, domain)
    return f":{color}-badge[{label}]"


def render_article_card(
    article: dict,
    saved_urls: set[str],
    key_prefix: str = "",
) -> None:
    """Render one article: title link, meta row, reason, AI summary expander, save button."""
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

        # Title row: clickable title + save/unsave toggle
        title_col, btn_col = st.columns([11, 1])
        with title_col:
            st.markdown(f"### [{title}]({url})")
        with btn_col:
            star  = "⭐" if is_saved else "☆"
            label = "Unsave" if is_saved else "Save"
            if st.button(star, key=f"{key_prefix}{url}", help=label, use_container_width=True):
                favs = load_favorites()
                if is_saved:
                    favs = remove_favorite(url, favs)
                else:
                    favs = add_favorite(article, favs)
                save_favorites(favs)
                st.rerun()

        # Meta row: source | domain | score | category
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"**{source}** &nbsp; {badge}")
        with c2:
            st.markdown(f"**{score}/10**")
        with c3:
            st.markdown(f"{icon} `{category}`")

        # One-line relevance hook
        st.caption(reason)

        # Expandable AI summary + actionable insights
        if summary or insights:
            with st.expander("AI Summary & Insights"):
                if summary:
                    st.markdown(summary)
                if insights:
                    st.markdown("**Actionable insights**")
                    for insight in insights:
                        st.markdown(f"- {insight}")

        st.divider()


# ── Subprocess fetch ──────────────────────────────────────────────────────────

def run_fetch() -> tuple[bool, str]:
    """Run fetch.py as a subprocess; return (success, combined stdout+stderr).
    Uses sys.executable so the same Python that runs Streamlit is used,
    and sets cwd to the repo root so relative paths (data/, fetch.py) resolve."""
    import sys
    repo_root = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "fetch.py")],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return result.returncode == 0, result.stdout + result.stderr


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_radar(digest: dict, favorites: dict) -> None:
    """Main page: FOMO stats banner, article list with filters applied from sidebar."""
    articles     = digest.get("articles", [])
    passed_count = digest.get("article_count", len(articles))
    # raw_count and dedup_count only exist in digests generated after the schema update.
    # Use None as sentinel so stale digests show "—" rather than a misleading number.
    raw_count    = digest.get("raw_count")
    dedup_count  = digest.get("dedup_count")
    filtered_out = (dedup_count - passed_count) if dedup_count is not None else None
    pct_str      = f"{int(100 * passed_count / dedup_count)}%" if dedup_count else "—"
    date_str, time_str = format_timestamp(digest["generated_at"])

    # ── FOMO stats ────────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Scanned today", raw_count if raw_count is not None else "—")
    with m2:
        st.metric("Made the cut", passed_count)
    with m3:
        st.metric("Filtered out", filtered_out if filtered_out is not None else "—")
    with m4:
        st.metric("Last updated", f"{date_str} {time_str}")

    if raw_count is not None:
        st.caption(
            f"We read **{raw_count} articles** across **{TOTAL_SOURCES} sources** so you "
            f"didn't have to. Only the top **{pct_str}** passed the relevance bar."
        )
    else:
        st.caption("Hit **Refresh now** to see full scan statistics.")

    # ── Apply filters from sidebar session state ──────────────────────────────
    cat_filter    = st.session_state.selected_categories or ALL_CATEGORIES
    domain_filter = st.session_state.selected_domains    or ALL_DOMAINS

    filtered = [
        a for a in articles
        if a["category"] in cat_filter and a["domain"] in domain_filter
    ]

    if st.session_state.sort_by == "Relevance":
        filtered.sort(key=lambda a: a["relevance_score"], reverse=True)
    else:
        filtered.sort(key=lambda a: (a["category"], -a["relevance_score"]))

    saved_urls = favorited_urls(favorites)
    count_word = "article" if len(filtered) == 1 else "articles"
    st.markdown(f"**Showing {len(filtered)} {count_word}**")

    if not filtered:
        st.warning("No articles match the current filters. Try widening your selection in the sidebar.")
        return

    for article in filtered:
        render_article_card(article, saved_urls, key_prefix="radar_")


def page_saved(favorites: dict) -> None:
    """Saved articles page: list with AI summary, comment box, and remove button."""
    st.title("⭐ Saved Articles")
    items = favorites.get("favorites", [])

    if not items:
        st.info(
            "No saved articles yet.\n\n"
            "Go to **📡 Radar** and click **☆** on any article to save it here."
        )
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

            # Title + remove button
            title_col, rm_col = st.columns([11, 1])
            with title_col:
                st.markdown(f"### [{title}]({url})")
            with rm_col:
                if st.button("🗑️", key=f"rm_{url}_{i}", help="Remove from saved", use_container_width=True):
                    updated = remove_favorite(url, load_favorites())
                    save_favorites(updated)
                    st.rerun()

            # Meta row
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f"**{source}** &nbsp; {badge}")
            with c2:
                st.markdown(f"**{score}/10**")
            with c3:
                st.markdown(f"{icon} `{category}`")

            if saved_at:
                try:
                    dt = datetime.fromisoformat(saved_at)
                    st.caption(f"Saved {dt.strftime('%Y-%m-%d %H:%M UTC')}")
                except Exception:
                    pass

            # AI summary + insights (collapsed)
            if summary or insights:
                with st.expander("AI Summary & Insights"):
                    if summary:
                        st.markdown(summary)
                    if insights:
                        st.markdown("**Actionable insights**")
                        for insight in insights:
                            st.markdown(f"- {insight}")

            # Notes / comment
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
                    updated = update_comment(url, new_comment, load_favorites())
                    save_favorites(updated)
                    st.toast("Note saved!", icon="✅")

            st.divider()


def page_profile() -> None:
    """Profile page: structured form that personalises scoring and AI insights."""
    st.title("Profile")
    st.markdown(
        "Your profile shapes how articles are scored and what insights the AI highlights. "
        "Fill in what applies — skip what doesn't."
    )
    st.info("Changes take effect after the next **Refresh now**.", icon="ℹ️")
    st.markdown("---")

    profile = load_profile()
    ts = profile.get("tech_stack", {})

    def _safe_default(value: list, options: list) -> list:
        """Filter a list to only include values present in options."""
        return [v for v in value if v in options]

    with st.form("profile_form"):

        # ── About You ────────────────────────────────────────────────────────
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

        # ── Tech Stack ───────────────────────────────────────────────────────
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

        # ── Client Domains ───────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Client Domains")
        client_domains = st.multiselect(
            "Domains you serve",
            options=DOMAIN_OPTIONS,
            default=_safe_default(profile.get("client_domains", []), DOMAIN_OPTIONS),
            label_visibility="collapsed",
        )

        # ── Active Projects ──────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Active Projects")
        st.caption("Up to 3 projects. These help the AI tailor insights to what you're actually building.")

        raw_projects = profile.get("projects", [{}, {}, {}])
        while len(raw_projects) < 3:
            raw_projects.append({})

        saved_projects = []
        for idx in range(3):
            p = raw_projects[idx]
            label = f"Project {idx + 1}"
            with st.expander(label, expanded=bool(p.get("name"))):
                p_name = st.text_input(
                    "Name", value=p.get("name", ""), key=f"p_name_{idx}",
                    placeholder="e.g. A-MATCH",
                )
                p_desc = st.text_input(
                    "One-line description", value=p.get("description", ""), key=f"p_desc_{idx}",
                    placeholder="What does it do and for whom?",
                )
                p_tech = st.multiselect(
                    "Key technologies",
                    options=PROJECT_TECH_OPTIONS,
                    default=_safe_default(p.get("tech", []), PROJECT_TECH_OPTIONS),
                    key=f"p_tech_{idx}",
                )
            saved_projects.append({"name": p_name, "description": p_desc, "tech": p_tech})

        # ── Topics ───────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Topics")
        tp_col1, tp_col2 = st.columns(2)
        with tp_col1:
            st.markdown("**Prioritise**")
            interests = st.multiselect(
                "prioritise",
                options=INTEREST_OPTIONS,
                default=_safe_default(profile.get("interests", []), INTEREST_OPTIONS),
                label_visibility="collapsed",
            )
        with tp_col2:
            st.markdown("**Exclude**")
            exclusions = st.multiselect(
                "exclude",
                options=EXCLUSION_OPTIONS,
                default=_safe_default(profile.get("exclusions", []), EXCLUSION_OPTIONS),
                label_visibility="collapsed",
            )

        # ── Filtering ────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Filtering")
        min_score = st.slider(
            "Minimum relevance score",
            min_value=5, max_value=9,
            value=profile.get("min_score", 7),
            help="Articles scoring below this are excluded from the digest.",
        )

        submitted = st.form_submit_button("Save Profile", use_container_width=True, type="primary")

    if submitted:
        new_profile = {
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
        }
        save_profile(new_profile)
        st.success("Profile saved.")
        st.info("Click **Refresh now** in the sidebar to apply your updated profile to the next digest.")


# ── Main ─────────────────────────────────────────────────────────────────────

def check_password() -> bool:
    """Show a password gate and return True only when the correct password is entered.
    The expected password is read from the APP_PASSWORD environment variable.
    If APP_PASSWORD is not set the gate is skipped (useful for local dev)."""
    expected = os.environ.get("APP_PASSWORD", "")
    if not expected:
        return True  # no password configured — open access (local dev)

    if st.session_state.get("authenticated"):
        return True

    st.set_page_config(page_title="GenAI Radar", layout="centered", page_icon="📡")
    st.title("GenAI Radar")
    st.markdown("---")
    pwd = st.text_input("Password", type="password", placeholder="Enter password to continue")
    if st.button("Sign in", use_container_width=True):
        if pwd == expected:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def main() -> None:
    if not check_password():
        st.stop()

    st.set_page_config(page_title="GenAI Radar", layout="wide", page_icon="📡")

    # Session state defaults — preserved across reruns
    defaults: dict = {
        "page":                "radar",
        "selected_categories": ALL_CATEGORIES.copy(),
        "selected_domains":    ALL_DOMAINS.copy(),
        "sort_by":             "Relevance",
        "profile_saved":       False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    digest    = load_digest()
    favorites = load_favorites()
    fav_count = len(favorites.get("favorites", []))

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("GenAI Radar")
        st.markdown("---")

        # Page navigation — three buttons, active one is disabled
        nav_col1, nav_col2, nav_col3 = st.columns(3)
        with nav_col1:
            if st.button(
                "Radar",
                use_container_width=True,
                disabled=(st.session_state.page == "radar"),
            ):
                st.session_state.page = "radar"
                st.rerun()
        with nav_col2:
            saved_label = f"Saved ({fav_count})" if fav_count else "Saved"
            if st.button(
                saved_label,
                use_container_width=True,
                disabled=(st.session_state.page == "saved"),
            ):
                st.session_state.page = "saved"
                st.rerun()
        with nav_col3:
            if st.button(
                "Profile",
                use_container_width=True,
                disabled=(st.session_state.page == "profile"),
            ):
                st.session_state.page = "profile"
                st.rerun()


        # Filters — only shown on Radar page
        if st.session_state.page == "radar" and digest is not None:
            st.markdown("**Filters**")
            st.session_state.selected_categories = st.multiselect(
                "Category",
                options=ALL_CATEGORIES,
                default=st.session_state.selected_categories,
                format_func=lambda c: f"{CATEGORY_ICONS.get(c, '')} {c}",
            )
            st.session_state.selected_domains = st.multiselect(
                "Domain",
                options=ALL_DOMAINS,
                default=st.session_state.selected_domains,
                format_func=lambda d: DOMAIN_LABELS.get(d, d),
            )
            st.session_state.sort_by = st.radio(
                "Sort by",
                options=["Relevance", "Category"],
                index=["Relevance", "Category"].index(st.session_state.sort_by),
            )
            st.markdown("---")

        # Refresh + meta
        if st.button("Refresh now", use_container_width=True):
            with st.spinner("Fetching and scoring articles… (~2–4 min)"):
                success, output = run_fetch()
            if success:
                st.success("Digest updated!")
            else:
                st.error("Fetch failed — see output below.")
            with st.expander("Fetch output"):
                st.text(output[-3000:])
            st.rerun()

        if digest:
            date_str, time_str = format_timestamp(digest["generated_at"])
            st.caption(f"Last fetch: {date_str} · {time_str}")
        else:
            st.caption("No digest yet")
        st.caption(f"Monitoring {TOTAL_SOURCES} sources")

    # ── Route to page ─────────────────────────────────────────────────────────
    if st.session_state.page == "saved":
        page_saved(favorites)
        return

    if st.session_state.page == "profile":
        page_profile()
        return

    # Radar page
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

    page_radar(digest, favorites)


if __name__ == "__main__":
    main()
