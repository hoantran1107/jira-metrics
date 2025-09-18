import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

API_CONTENT_PATH = "/rest/api/content"

load_dotenv()


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


def _get_confluence_base_url() -> str:
    base = os.getenv("CONFLUENCE_SERVER")
    if not base:
        # Fallback: Jira base + /wiki
        jira_server = _require_env("JIRA_SERVER")
        base = jira_server.rstrip("/") + "/wiki"
    return base.rstrip("/")


def _get_confluence_auth() -> Tuple[str, str]:
    email = os.getenv("CONFLUENCE_EMAIL") or _require_env("JIRA_EMAIL")
    token = os.getenv("CONFLUENCE_API_TOKEN") or _require_env("JIRA_API_TOKEN")
    return email, token


def _request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = _get_confluence_base_url()
    url = f"{base}{path}"
    email, token = _get_confluence_auth()
    headers = {"Accept": "application/json"}
    resp = requests.request(
        method, url, params=params, json=json, auth=(email, token), headers=headers
    )
    resp.raise_for_status()
    if resp.status_code == 204:
        return {}
    return resp.json()


def find_page_by_title(space_key: str, title: str) -> Optional[Dict[str, Any]]:
    params = {
        "spaceKey": space_key,
        "title": title,
        "expand": "version,body.storage",
        "limit": 1,
    }
    data = _request("GET", API_CONTENT_PATH, params=params)
    results = data.get("results", [])
    return results[0] if results else None


def list_space_pages(space_key: str, *, limit: int = 250) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []
    start = 0
    while True:
        params = {
            "spaceKey": space_key,
            "type": "page",
            "start": start,
            "limit": min(limit - len(pages), 50),
            "expand": "body.storage",
        }
        if params["limit"] <= 0:
            break
        data = _request("GET", API_CONTENT_PATH, params=params)
        chunk = data.get("results", [])
        pages.extend(chunk)
        if not chunk or len(pages) >= limit:
            break
        start = start + len(chunk)
    return pages[:limit]


def _page_payload(
    *,
    title: str,
    space_key: str,
    html_body: str,
    parent_page_id: Optional[str] = None,
    version_number: Optional[int] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": html_body, "representation": "storage"}},
    }
    if parent_page_id:
        payload["ancestors"] = [{"id": str(parent_page_id)}]
    if version_number is not None:
        payload["version"] = {"number": int(version_number)}
    return payload


def create_or_update_page(
    *,
    space_key: str,
    title: str,
    html_body: str,
    parent_page_id: Optional[str] = None,
) -> Dict[str, Any]:
    existing = find_page_by_title(space_key, title)
    if existing:
        page_id = existing.get("id")
        current_version = int(existing.get("version", {}).get("number", 1))
        payload = _page_payload(
            title=title,
            space_key=space_key,
            html_body=html_body,
            parent_page_id=parent_page_id,
            version_number=current_version + 1,
        )
        data = _request("PUT", f"{API_CONTENT_PATH}/{page_id}", json=payload)
        return data
    payload = _page_payload(
        title=title,
        space_key=space_key,
        html_body=html_body,
        parent_page_id=parent_page_id,
    )
    data = _request("POST", API_CONTENT_PATH, json=payload)
    return data


def _strip_html_tags(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_space_corpus(space_key: str, *, limit: int = 200) -> List[Dict[str, str]]:
    pages = list_space_pages(space_key, limit=limit)
    corpus: List[Dict[str, str]] = []
    for p in pages:
        title = p.get("title", "")
        body = p.get("body", {}).get("storage", {}).get("value", "")
        text = _strip_html_tags(body or "")
        if text:
            corpus.append({"id": p.get("id", ""), "title": title, "text": text})
    return corpus
