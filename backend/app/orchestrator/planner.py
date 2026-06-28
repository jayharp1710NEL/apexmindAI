"""Planner: turn a goal into a strict-JSON Plan via the LLM.

Uses task_type `structured_json` with json_mode and the versioned orchestrator
prompt. Robust to minor formatting (code fences, surrounding prose) and degrades to
a single-step plan if the model returns something unparseable.
"""

from __future__ import annotations

import json
import logging

from app.orchestrator.plan import Plan
from app.prompts.registry import get_active_prompt
from app.router.interface import LLMInterface

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from model output."""
    text = text.strip()
    if text.startswith("```"):
        # strip a ```json ... ``` fence
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def _available_models() -> list[str]:
    """List installed local (Ollama) model ids so the boss can assign them."""
    from app.config import settings

    if not settings.local_openai_base_url:
        return []
    try:
        import httpx

        base = settings.local_openai_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=4) as c:
            resp = await c.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {settings.local_openai_api_key or 'x'}"},
            )
        return [m["id"] for m in resp.json().get("data", []) if m.get("id")]
    except Exception:
        return []


async def generate_plan(
    llm: LLMInterface,
    goal: str,
    *,
    session_factory=None,
    max_tokens: int = 1200,
) -> Plan:
    system = await get_active_prompt("orchestrator", session_factory)
    models = await _available_models()
    if models:
        system += (
            "\n\nLocal models you may assign per step via \"model\" (provider "
            '"local"). Pick the best specialist for each step; assign different '
            "models to independent steps so they run in parallel:\n- "
            + "\n- ".join(models)
        )
    resp = await llm.generate(
        "orchestration",  # the boss model plans the work
        prompt=goal,
        system=system,
        json_mode=True,
        max_tokens=max_tokens,
        temperature=0.2,
    )
    try:
        data = extract_json(resp.text)
        plan = Plan.model_validate(data)
        if not plan.steps:
            return Plan.single(goal)
        return plan
    except Exception as exc:  # never crash a run on a bad plan
        logger.warning("plan parse failed (%r); using single-step plan", exc)
        return Plan.single(goal)
