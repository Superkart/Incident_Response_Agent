"""
Quick Analysis Agent — fast baseline analysis using only Prometheus metrics and recent logs.
Always runs before the full pipeline, so on-call engineers get an immediate signal
even if the deep pipeline is slow or fails.
"""
import logging

from agents.llm import _client
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM = """You are an incident response agent doing a rapid first-look analysis.
Be concise and specific. Answer in plain text (not JSON):
1. What went wrong?
2. What is the likely root cause?
3. What should the on-call engineer check first?"""


async def run(context: dict) -> str:
    service = context.get("service", "unknown")
    alert_name = context.get("alertname", "unknown")
    summary = context.get("summary", "")
    prometheus_snapshot = context.get("prometheus_snapshot", {})
    recent_logs = context.get("recent_logs", [])

    logs_text = "\n".join(recent_logs) if recent_logs else "No logs available."
    user_msg = (
        f"Alert: {alert_name}\n"
        f"Service: {service}\n"
        f"Summary: {summary}\n\n"
        f"Prometheus metrics:\n{prometheus_snapshot}\n\n"
        f"Recent logs:\n{logs_text}"
    )

    try:
        response = await _client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        return response.choices[0].message.content or "No analysis available."
    except Exception as exc:
        logger.warning("quick_analysis failed: %s", exc)
        return f"Quick analysis unavailable: {exc}"
