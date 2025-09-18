from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import pandas as pd


@dataclass
class MetricsResult:
    df: pd.DataFrame
    throughput: pd.Series
    velocity: pd.Series
    reopen_rate_pct: float
    avg_cycle_time_days: Optional[float]
    avg_lead_time_days: Optional[float]
    cycle_time_std_days: Optional[float]
    blocked_avg_days: Optional[float]


def _first_time_to_status(
    history: List[Tuple[pd.Timestamp, Optional[str], Optional[str]]], targets: Set[str]
) -> Optional[pd.Timestamp]:
    for t, _from, to in history:
        if to in targets:
            return t
    return None


def _last_time_to_status(
    history: List[Tuple[pd.Timestamp, Optional[str], Optional[str]]], targets: Set[str]
) -> Optional[pd.Timestamp]:
    for t, _from, to in reversed(history):
        if to in targets:
            return t
    return None


def _was_reopened(
    history: List[Tuple[pd.Timestamp, Optional[str], Optional[str]]],
    done_names: Set[str],
) -> bool:
    seen_done = False
    for _, _from, to in history:
        if to in done_names:
            seen_done = True
        elif seen_done and (to not in done_names):
            return True
    return False


def compute_all_metrics(
    df: pd.DataFrame,
    *,
    in_progress_names: Set[str],
    done_names: Set[str],
) -> MetricsResult:
    dfm = df.copy()

    # Timestamps for in-progress and done
    in_prog_times = dfm["status_history"].apply(
        lambda h: _first_time_to_status(h, in_progress_names)
    )

    # Done time preference: resolutiondate if available, else last transition to done status
    last_done_times = dfm["status_history"].apply(
        lambda h: _last_time_to_status(h, done_names)
    )
    resolved_times = dfm.get("resolved")
    done_times = resolved_times.where(resolved_times.notna(), last_done_times)

    dfm["in_progress_time"] = in_prog_times
    dfm["done_time"] = done_times

    # Cycle time (days)
    dfm["cycle_time_days"] = (
        dfm["done_time"] - dfm["in_progress_time"]
    ).dt.total_seconds() / 86400.0

    # Lead time (days): resolution - creation
    if "created" in dfm.columns and "resolved" in dfm.columns:
        dfm["lead_time_days"] = (
            dfm["resolved"] - dfm["created"]
        ).dt.total_seconds() / 86400.0

    # Reopen rate among completed issues
    reopened_flags = dfm["status_history"].apply(lambda h: _was_reopened(h, done_names))
    completed_mask = dfm["done_time"].notna()
    completed_total = int(completed_mask.sum())
    reopened_total = int((reopened_flags & completed_mask).sum())
    reopen_rate_pct: float = (
        (reopened_total / completed_total * 100.0) if completed_total > 0 else 0.0
    )

    # Throughput and velocity per sprint (only for completed issues with sprint_id)
    completed = dfm[completed_mask]
    completed_with_sprint = (
        completed.dropna(subset=["sprint_id"])
        if "sprint_id" in completed.columns
        else completed.iloc[0:0]
    )

    if not completed_with_sprint.empty:
        throughput = completed_with_sprint.groupby("sprint_id").size()
        # story_points may be None/NaN
        velocity = completed_with_sprint.groupby("sprint_id")["story_points"].sum(
            min_count=1
        )
        velocity = velocity.fillna(0.0)
    else:
        throughput = pd.Series(dtype=int)
        velocity = pd.Series(dtype=float)

    # Averages
    cycle_series = dfm["cycle_time_days"].dropna()
    lead_series = (
        dfm["lead_time_days"].dropna()
        if "lead_time_days" in dfm
        else pd.Series(dtype=float)
    )

    avg_cycle = float(cycle_series.mean()) if len(cycle_series) else None
    avg_lead = float(lead_series.mean()) if len(lead_series) else None
    cycle_std = float(cycle_series.std(ddof=1)) if len(cycle_series) > 1 else None

    blocked_avg = None
    if "blocked_days" in dfm.columns:
        b = dfm["blocked_days"].dropna()
        blocked_avg = float(b.mean()) if len(b) else None

    return MetricsResult(
        df=dfm,
        throughput=throughput,
        velocity=velocity,
        reopen_rate_pct=reopen_rate_pct,
        avg_cycle_time_days=avg_cycle,
        avg_lead_time_days=avg_lead,
        cycle_time_std_days=cycle_std,
        blocked_avg_days=blocked_avg,
    )
