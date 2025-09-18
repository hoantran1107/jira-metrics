# Jira Metrics Dashboard PoC

A local Streamlit app that connects to Jira Cloud, fetches recent sprint data, computes delivery metrics, and visualizes results.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- Jira Cloud API token and Jira email
- Jira project key and board ID

## Setup (Windows PowerShell)

1. Clone this repo and open a shell in the project folder.

2. Install dependencies and create virtual environment with uv:

   ```powershell
   uv sync
   ```

3. Configure environment:
   - Copy `env.sample` to `.env` and fill in values.

     ```powershell
     Copy-Item env.sample .env
     notepad .env
     ```

   - Or set env vars in PowerShell for the current session:

     ```powershell
     $env:JIRA_SERVER = "https://your-domain.atlassian.net"
     $env:JIRA_EMAIL = "you@example.com"
     $env:JIRA_API_TOKEN = "YOUR_TOKEN"
     $env:JIRA_PROJECT_KEY = "PROJ"
     $env:JIRA_BOARD_ID = "123"
     $env:SPRINT_LOOKBACK = "5"
     $env:STORY_POINTS_FIELD_ID = "customfield_10016"
     $env:SPRINT_FIELD_ID = "customfield_10007"
     ```

## Run the dashboard

```powershell
uv run streamlit run app.py
```

The app will open in your default browser. Use the sidebar controls to fetch data for the last N closed sprints.

## AI-Powered Sprint Feedback (optional)

- Set `OPENAI_API_KEY` in your environment to enable AI-generated sprint feedback.
- Optionally set Confluence variables to publish results to a page and to use RAG:

  ```powershell
  $env:CONFLUENCE_SERVER = "https://your-domain.atlassian.net/wiki"
  $env:CONFLUENCE_EMAIL = "you@example.com"
  $env:CONFLUENCE_API_TOKEN = "YOUR_TOKEN"
  $env:CONFLUENCE_SPACE_KEY = "ENG"
  # Optional parent page ID to nest under
  $env:CONFLUENCE_PARENT_PAGE_ID = "123456"
  $env:OPENAI_API_KEY = "sk-..."
  $env:OPENAI_MODEL = "gpt-4o-mini"
  ```

When enabled, use the "AI-Powered Sprint Feedback" section in the app to generate a concise retrospective using your metrics, optionally grounded with Confluence context via BM25 retrieval, then publish to Confluence.

## Notes

- Story points and sprint fields often differ per Jira site. Adjust `STORY_POINTS_FIELD_ID` and `SPRINT_FIELD_ID` if needed.
- If the Jira client agile methods are unavailable, the app falls back to REST calls.
- RAG retrieval uses simple BM25 ranking over Confluence pages in the specified space. For more on RAG patterns, see the Prompt Engineering Guide on RAG: [RAG Overview](https://www.promptingguide.ai/research/rag).
- For insights on effective sprint retrospectives with Jira/Confluence, see Atlassian's guide: [Conduct effective sprint retros](https://www.atlassian.com/blog/confluence/effective-sprint-retros-with-confluence-and-jira).
- To fetch Confluence content via the REST API, see an example tutorial: [Using the Confluence API to Get Space Pages in Python](https://endgrate.com/blog/using-the-confluence-api-to-get-space-pages-in-python).
- To speed up LLM responses, we use a simple filesystem cache (DiskCache). See: [Caching Responses with Python and DiskCache](https://medium.com/@Shamimw/speed-up-your-llm-apps-caching-responses-with-python-and-diskcache-aef146a410d5).
