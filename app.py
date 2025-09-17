import os

import streamlit as st
from dotenv import load_dotenv

from data_processing import (
    build_issue_rows_dataframe,
    compute_status_durations_column,
)
from jira_client import fetch_issues_for_sprints, get_closed_sprint_ids
from metrics import compute_all_metrics
from report import generate_summary_markdown

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
        df = build_issue_rows_dataframe(issues)
        df = compute_status_durations_column(df)

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
    st.markdown(generate_summary_markdown(metrics))

else:
    st.info("Configure inputs in the sidebar and click 'Fetch / Refresh Data'.")
