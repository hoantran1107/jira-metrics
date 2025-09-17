# Jira Metrics Dashboard PoC

A local Streamlit app that connects to Jira Cloud, fetches recent sprint data, computes delivery metrics, and visualizes results.

## Prerequisites

- Python 3.10+
- Jira Cloud API token and Jira email
- Jira project key and board ID

## Setup (Windows PowerShell)

1. Clone this repo and open a shell in the project folder.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Configure environment:
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
streamlit run app.py
```

The app will open in your default browser. Use the sidebar controls to fetch data for the last N closed sprints.

## Notes

- Story points and sprint fields often differ per Jira site. Adjust `STORY_POINTS_FIELD_ID` and `SPRINT_FIELD_ID` if needed.
- If the Jira client agile methods are unavailable, the app falls back to REST calls.
