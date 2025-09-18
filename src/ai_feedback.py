import hashlib
import os
from typing import Optional

from dotenv import load_dotenv

from src.metrics import MetricsResult

load_dotenv()

_CACHE = None
try:
    from diskcache import Cache  # type: ignore

    _CACHE = Cache(os.getenv("CACHE_DIR", ".cache"))
except Exception:  # pragma: no cover
    _CACHE = None


def _stable_metrics_signature(m: MetricsResult) -> str:
    parts = []
    parts.append(f"avg_cycle={m.avg_cycle_time_days}")
    parts.append(f"avg_lead={m.avg_lead_time_days}")
    parts.append(f"cycle_std={m.cycle_time_std_days}")
    parts.append(f"reopen={m.reopen_rate_pct}")
    parts.append(
        "throughput="
        + ",".join([f"{int(k)}:{int(v)}" for k, v in m.throughput.items()])
        if not m.throughput.empty
        else "throughput="
    )
    parts.append(
        "velocity="
        + ",".join([f"{int(k)}:{float(v):.1f}" for k, v in m.velocity.items()])
        if not m.velocity.empty
        else "velocity="
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest


def _build_prompt(summary_markdown: str, rag_context: Optional[str]) -> str:
    prompt = [
        "You are an experienced Agile coach.",
        "Given the team's sprint metrics, write a concise, actionable sprint retrospective analysis:",
        "- Identify 3-5 key insights (what went well, what to improve)",
        "- Give 3 concrete, high-leverage recommendations",
        "- Keep it pragmatic and non-generic; tie each point to the metrics.",
        "\nSprint Metrics Summary (Markdown):\n",
        summary_markdown,
    ]
    if rag_context:
        prompt.append("\nRelevant internal context from Confluence:\n")
        prompt.append(rag_context)
    prompt.append("\nOutput as Markdown with headings and bullet points.")
    return "\n".join(prompt)


def generate_ai_feedback(
    *,
    metrics: MetricsResult,
    summary_markdown: str,
    rag_context: Optional[str] = None,
) -> str:
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "openai package is required. Add it to dependencies and set OPENAI_API_KEY."
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _build_prompt(summary_markdown, rag_context)

    key_source = f"model={model}|sig={_stable_metrics_signature(metrics)}|rag={hashlib.sha256((rag_context or '').encode('utf-8')).hexdigest()}|prompt={hashlib.sha256(prompt.encode('utf-8')).hexdigest()}"
    cache_key = f"ai_feedback:{hashlib.sha256(key_source.encode('utf-8')).hexdigest()}"

    if _CACHE is not None:
        cached = _CACHE.get(cache_key)
        if cached:
            return cached

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    text = completion.choices[0].message.content or ""

    if _CACHE is not None:
        _CACHE.set(cache_key, text, expire=int(os.getenv("AI_CACHE_TTL", "86400")))
    return text
