from typing import List

from metrics import MetricsResult


def _fmt_days(value) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{value:.1f}d"
    except Exception:
        return "n/a"


def generate_summary_markdown(m: MetricsResult) -> str:
    lines: List[str] = []
    lines.append("**Summary of Metrics (Last Sprints):**")
    lines.append(
        f"- **Average cycle time**: {_fmt_days(m.avg_cycle_time_days)}; **lead time**: {_fmt_days(m.avg_lead_time_days)}; **cycle time stdev**: {_fmt_days(m.cycle_time_std_days)}"
    )
    if m.blocked_avg_days is not None:
        lines.append(
            f"- **Avg blocked time**: {_fmt_days(m.blocked_avg_days)} per ticket"
        )
    lines.append(f"- **Reopen rate**: {m.reopen_rate_pct:.1f}%")
    if not m.throughput.empty:
        lines.append(
            f"- **Throughput** (tickets/sprint): {', '.join([f'{int(i)}:{int(v)}' for i, v in m.throughput.items()])}"
        )
    if not m.velocity.empty:
        lines.append(
            f"- **Velocity** (SP/sprint): {', '.join([f'{int(i)}:{float(v):.1f}' for i, v in m.velocity.items()])}"
        )

    # Basic recommendations heuristics
    recs: List[str] = []
    if (
        m.avg_cycle_time_days
        and m.avg_lead_time_days
        and m.avg_lead_time_days - m.avg_cycle_time_days > 2.0
    ):
        recs.append(
            "Reduce waiting time before work starts; clarify backlog grooming and prioritization."
        )
    if m.blocked_avg_days and m.blocked_avg_days > 0.5:
        recs.append(
            "Investigate frequent blockers; define escalation paths and remove systemic impediments."
        )
    if m.reopen_rate_pct > 10.0:
        recs.append(
            "Tighten acceptance criteria and improve QA to reduce reopen churn."
        )
    if m.cycle_time_std_days and m.cycle_time_std_days > 3.0:
        recs.append(
            "High variance in cycle time; slice work smaller and limit WIP for predictability."
        )

    if recs:
        lines.append("\n**Recommendations:**")
        for r in recs[:3]:
            lines.append(f"- {r}")

    return "\n".join(lines)
