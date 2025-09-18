import os

import streamlit as st
from dotenv import load_dotenv

from src.ai_feedback import generate_ai_feedback
from src.confluence_client import create_or_update_page
from src.data_processing import (
    build_issue_rows_dataframe,
    compute_status_durations_column,
)
from src.jira_client import fetch_issues_for_sprints, get_closed_sprint_ids
from src.metrics import compute_all_metrics
from src.rag import retrieve_confluence_context
from src.report import generate_summary_markdown

try:
    import streamlit.runtime.caching as st_caching  # type: ignore
except Exception:  # pragma: no cover
    st_caching = None

load_dotenv()

st.set_page_config(page_title="Jira Sprint Metrics Dashboard", layout="wide")

# Sidebar configuration
st.sidebar.header("Configuration")
server_default = os.getenv("JIRA_SERVER", "https://your-domain.atlassian.net")
email_default = os.getenv("JIRA_EMAIL", "you@example.com")
project_default = os.getenv("JIRA_PROJECT_KEY", "PROJ")
board_default = int(os.getenv("JIRA_BOARD_ID", "0") or 0)
lookback_default = int(os.getenv("SPRINT_LOOKBACK", "5") or 5)

st.sidebar.text_input("Jira Server", value=server_default, disabled=True)
st.sidebar.text_input("Email", value=email_default, disabled=True)
project_key = st.sidebar.text_input("Project Key", value=project_default)
board_id = st.sidebar.number_input("Board ID", min_value=0, step=1, value=board_default)
lookback = st.sidebar.slider(
    "Closed sprints lookback", min_value=1, max_value=15, value=lookback_default
)

in_progress_names = st.sidebar.multiselect(
    "In-Progress Status Names",
    options=["In Progress", "In-Progress", "Doing"],
    default=["In Progress"],
)

done_names = st.sidebar.multiselect(
    "Done Status Names",
    options=["Done", "Closed", "Resolved"],
    default=["Done", "Closed", "Resolved"],
)

fetch_button = st.sidebar.button("Fetch / Refresh Data", type="primary")

st.title("Jira Sprint Metrics Dashboard")

if fetch_button:
    if board_id <= 0:
        st.error("Please provide a valid Board ID.")
        st.stop()

    with st.spinner("Fetching sprint list..."):
        sprint_ids = get_closed_sprint_ids(
            board_id=int(board_id), lookback=int(lookback)
        )
    if not sprint_ids:
        st.warning("No closed sprints found for this board.")
        st.stop()

    with st.spinner("Fetching issues and changelogs..."):
        issues = fetch_issues_for_sprints(
            project_key=project_key, sprint_ids=sprint_ids
        )

    with st.spinner("Processing data..."):

        @st.cache_data(show_spinner=False)
        def _cached_process(_issues):
            _df = build_issue_rows_dataframe(_issues)
            _df = compute_status_durations_column(_df)
            return _df

        df = _cached_process(issues)

    with st.spinner("Computing metrics..."):
        metrics = compute_all_metrics(
            df, in_progress_names=set(in_progress_names), done_names=set(done_names)
        )

    # Layout: two columns for charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Cycle Time (days) Distribution")
        if "cycle_time_days" in metrics.df.columns:  # type: ignore[attr-defined]
            st.bar_chart(metrics.df["cycle_time_days"].dropna())  # type: ignore[attr-defined]
        else:
            st.info("No cycle time data available.")

        st.subheader("Throughput per Sprint (tickets)")
        if not metrics.throughput.empty:
            st.bar_chart(metrics.throughput)
        else:
            st.info("No throughput data.")

    with col2:
        st.subheader("Velocity per Sprint (story points)")
        if not metrics.velocity.empty:
            st.line_chart(metrics.velocity)
        else:
            st.info("No velocity data.")

        st.subheader("Reopen Rate")
        st.metric("Reopen %", f"{metrics.reopen_rate_pct:.1f}%")

    st.subheader("Top Issues by Blocked Time")
    if "blocked_days" in metrics.df.columns:  # type: ignore[attr-defined]
        top_blocked = (
            metrics.df[["key", "blocked_days"]]  # type: ignore[attr-defined]
            .dropna()
            .sort_values("blocked_days", ascending=False)
            .head(10)
        )
        st.dataframe(top_blocked, use_container_width=True)
    else:
        st.info("No blocked status data.")

    st.subheader("Summary & Recommendations")
    summary_md = generate_summary_markdown(metrics)
    st.markdown(summary_md)

    st.divider()
    st.subheader("AI-Powered Sprint Feedback")
    colA, colB = st.columns([1, 1])
    with colA:
        confluence_space = st.text_input(
            "Confluence Space Key", value=os.getenv("CONFLUENCE_SPACE_KEY", "")
        )
        confluence_parent_id = st.text_input(
            "Parent Page ID (optional)",
            value=os.getenv("CONFLUENCE_PARENT_PAGE_ID", ""),
        )
        publish_title_default = (
            f"Sprint Insights - Board {int(board_id)} (Last {int(lookback)})"
        )
        page_title = st.text_input("Confluence Page Title", value=publish_title_default)
        include_rag = st.checkbox("Use Confluence context (RAG)", value=True)

    with colB:
        generate_btn = st.button("Generate AI Feedback", type="primary")
        publish_btn = st.button("Publish to Confluence")

    ai_feedback = st.session_state.get("ai_feedback_text")
    if generate_btn:
        with st.spinner("Generating AI feedback..."):
            rag_context = None
            if include_rag and confluence_space:
                rag_context = retrieve_confluence_context(
                    space_key=confluence_space, summary_markdown=summary_md
                )
            try:
                ai_feedback = generate_ai_feedback(
                    metrics=metrics,
                    summary_markdown=summary_md,
                    rag_context=rag_context,
                )
                st.session_state["ai_feedback_text"] = ai_feedback
            except Exception as e:
                st.error(f"AI generation failed: {e}")
    if ai_feedback:
        st.markdown(ai_feedback)

    if publish_btn:
        if not confluence_space or not page_title:
            st.error("Provide Confluence space key and page title.")
        else:
            with st.spinner("Publishing to Confluence..."):
                try:
                    # Combine summary + AI analysis
                    content_md = f"{summary_md}\n\n---\n\n{ai_feedback or ''}"
                    # Convert Markdown to basic HTML for storage representation
                    try:
                        import markdown as md  # type: ignore

                        content_html = md.markdown(content_md)
                    except Exception:
                        # Minimal fallback: wrap in <pre>
                        content_html = f"<pre>{content_md}</pre>"
                    result = create_or_update_page(
                        space_key=confluence_space,
                        title=page_title,
                        html_body=content_html,
                        parent_page_id=confluence_parent_id or None,
                    )
                    link = result.get("_links", {}).get("base", "") + result.get(
                        "_links", {}
                    ).get("webui", "")
                    if link:
                        st.success(f"Published to Confluence: {link}")
                    else:
                        st.success("Published to Confluence.")
                except Exception as e:
                    st.error(f"Publish failed: {e}")

else:
    st.info("Configure inputs in the sidebar and click 'Fetch / Refresh Data'.")
