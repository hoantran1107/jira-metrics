import os
from typing import Iterable, List

import requests
from dotenv import load_dotenv

try:
    from jira import JIRA  # type: ignore
except Exception:  # pragma: no cover
    JIRA = None  # fallback only if library missing at import time

load_dotenv()


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


def get_jira_client():
    """Create and return an authenticated Jira client using basic auth (email + API token)."""
    server = _require_env("JIRA_SERVER")
    email = _require_env("JIRA_EMAIL")
    token = _require_env("JIRA_API_TOKEN")

    if JIRA is None:
        raise RuntimeError("jira library not installed. Run: pip install jira")

    options = {"server": server}
    return JIRA(options=options, basic_auth=(email, token))


def get_closed_sprint_ids(board_id: int, lookback: int = 5) -> List[int]:
    """Return the IDs of the last N closed sprints for a board.

    Tries the jira client's agile API first, then falls back to REST if needed.
    """
    server = _require_env("JIRA_SERVER")
    email = _require_env("JIRA_EMAIL")
    token = _require_env("JIRA_API_TOKEN")

    try:
        jira = get_jira_client()
        sprints = jira.sprints(board_id, state="closed")  # type: ignore[attr-defined]
        ids = [int(s.id) for s in sprints]
        return ids[-lookback:]
    except Exception:
        # Fallback to REST
        url = f"{server}/rest/agile/1.0/board/{board_id}/sprint"
        params = {"state": "closed", "startAt": 0, "maxResults": 50}
        ids: List[int] = []
        while True:
            resp = requests.get(url, params=params, auth=(email, token))
            resp.raise_for_status()
            data = resp.json()
            for s in data.get("values", []):
                if "id" in s:
                    ids.append(int(s["id"]))
            if data.get("isLast"):
                break
            params["startAt"] = int(params["startAt"]) + int(params["maxResults"])  # type: ignore
        return ids[-lookback:]


def _search_issues_with_changelog(jira, jql: str, batch_size: int = 100):
    start_at = 0
    results = []
    while True:
        chunk = jira.search_issues(
            jql, startAt=start_at, maxResults=batch_size, expand="changelog"
        )
        if not chunk:
            break
        results.extend(chunk)
        start_at += len(chunk)
        if len(chunk) < batch_size:
            break
    return results


def fetch_issues_for_sprints(project_key: str, sprint_ids: Iterable[int]):
    """Fetch all issues for the given sprint IDs with changelogs expanded."""
    jira = get_jira_client()
    all_issues = []
    for sid in sprint_ids:
        jql = f'project = "{project_key}" AND sprint = {int(sid)}'
        all_issues.extend(_search_issues_with_changelog(jira, jql))
    return all_issues
