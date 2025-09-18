import os
import re
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def _get_story_points_field_id() -> str:
    return os.getenv("STORY_POINTS_FIELD_ID", "customfield_10016")


def _get_sprint_field_id() -> str:
    return os.getenv("SPRINT_FIELD_ID", "customfield_10007")


def _parse_datetime(value: Any) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    try:
        ts = pd.to_datetime(value, utc=True)
        return ts.tz_localize(None) if ts.tzinfo else ts
    except Exception:
        return None


def _extract_story_points(fields: Any) -> Optional[float]:
    sp_field = _get_story_points_field_id()
    try:
        value = getattr(fields, sp_field, None)
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None
    except Exception:
        return None


def _extract_sprint_id(fields: Any) -> Optional[int]:
    """Attempt to extract sprint ID from the Sprint custom field.

    Handles lists of dicts/objects/strings. Returns the most recent/last sprint id if available.
    """
    sprint_field = _get_sprint_field_id()
    try:
        raw = getattr(fields, sprint_field, None)
    except Exception:
        raw = None
    if raw is None:
        return None

    sprint_ids: List[int] = []

    def maybe_add(val: Any):
        try:
            if isinstance(val, dict) and "id" in val:
                sprint_ids.append(int(val["id"]))
            elif hasattr(val, "id"):
                sprint_ids.append(int(getattr(val, "id")))
            elif isinstance(val, str):
                m = re.search(r"id=(\d+)", val)
                if m:
                    sprint_ids.append(int(m.group(1)))
        except Exception:
            pass

    if isinstance(raw, list):
        for item in raw:
            maybe_add(item)
    else:
        maybe_add(raw)

    if not sprint_ids:
        return None
    # Heuristic: pick the largest ID (most recent) or simply the last
    return sorted(sprint_ids)[-1]


def _extract_status_history(
    issue: Any,
) -> List[Tuple[pd.Timestamp, Optional[str], Optional[str]]]:
    history: List[Tuple[pd.Timestamp, Optional[str], Optional[str]]] = []
    try:
        for hist in getattr(issue, "changelog").histories:  # type: ignore[attr-defined]
            ht = _parse_datetime(getattr(hist, "created", None))
            if ht is None:
                continue
            for item in getattr(hist, "items", []):
                try:
                    if getattr(item, "field", None) == "status":
                        history.append(
                            (
                                ht,
                                getattr(item, "fromString", None),
                                getattr(item, "toString", None),
                            )
                        )
                except Exception:
                    continue
    except Exception:
        pass
    history.sort(key=lambda t: t[0])
    return history


def build_issue_rows_dataframe(issues: Iterable[Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for issue in issues:
        try:
            fields = getattr(issue, "fields")
        except Exception:
            continue
        key = getattr(issue, "key", None)
        created = _parse_datetime(getattr(fields, "created", None))
        resolved = _parse_datetime(getattr(fields, "resolutiondate", None))
        assignee_name = None
        try:
            assignee = getattr(fields, "assignee", None)
            if assignee is not None:
                assignee_name = getattr(assignee, "displayName", None)
        except Exception:
            assignee_name = None
        issuetype_name = None
        try:
            issuetype = getattr(fields, "issuetype", None)
            if issuetype is not None:
                issuetype_name = getattr(issuetype, "name", None)
        except Exception:
            issuetype_name = None

        story_points = _extract_story_points(fields)
        sprint_id = _extract_sprint_id(fields)
        status_history = _extract_status_history(issue)

        rows.append(
            {
                "key": key,
                "assignee": assignee_name,
                "issuetype": issuetype_name,
                "story_points": story_points,
                "created": created,
                "resolved": resolved,
                "sprint_id": sprint_id,
                "status_history": status_history,
            }
        )

    df = pd.DataFrame(rows)
    return df


def _time_in_status(
    history: List[Tuple[pd.Timestamp, Optional[str], Optional[str]]],
) -> Dict[str, timedelta]:
    durations: Dict[str, timedelta] = {}
    if not history or len(history) < 2:
        return durations
    for idx in range(len(history) - 1):
        start_time, _from, to_status = history[idx]
        end_time, _from2, _to2 = history[idx + 1]
        if to_status is None:
            continue
        delta = end_time - start_time
        durations[to_status] = durations.get(to_status, timedelta()) + delta
    return durations


def compute_status_durations_column(df: pd.DataFrame) -> pd.DataFrame:
    durations = df["status_history"].apply(_time_in_status)
    df = df.copy()
    df["status_durations"] = durations
    # Blocked time in days (float)
    blocked_days: List[Optional[float]] = []
    for dur in durations:
        total = timedelta()
        for status_name, td in dur.items():
            if status_name and "blocked" in status_name.lower():
                total += td
        blocked_days.append(total.total_seconds() / 86400.0 if total else None)
    df["blocked_days"] = blocked_days
    return df
