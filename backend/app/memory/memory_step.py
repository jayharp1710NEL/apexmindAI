"""Conservative memory step: extract durable facts from a conversation.

Uses the strict-JSON memory prompt. Conservative by design: facts below a
confidence threshold (or missing key/value) are dropped, so we remember little and
only when sure. The conversation is untrusted DATA — instructions in it are ignored.
"""

from __future__ import annotations

import uuid

from app.memory.facts import upsert_fact
from app.orchestrator.planner import extract_json
from app.prompts.registry import get_active_prompt


def _conversation_text(conversation) -> str:
    if isinstance(conversation, str):
        return conversation
    parts = []
    for m in conversation:
        role = getattr(m, "role", None) or m.get("role", "user")
        content = getattr(m, "content", None) or m.get("content", "")
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


async def extract_and_store_facts(
    *,
    llm,
    session_factory,
    project_id: uuid.UUID,
    conversation,
    min_confidence: float = 0.6,
) -> list[dict]:
    system = await get_active_prompt("memory", session_factory)
    resp = await llm.generate(
        "structured_json",
        prompt=_conversation_text(conversation),
        system=system,
        json_mode=True,
        max_tokens=500,
        temperature=0.0,
    )
    try:
        data = extract_json(resp.text)
    except Exception:
        return []
    facts = data.get("facts", []) if isinstance(data, dict) else []

    stored: list[dict] = []
    async with session_factory() as s, s.begin():
        for f in facts:
            key = (f.get("key") or "").strip()
            value = (f.get("value") or "").strip()
            confidence = float(f.get("confidence", 0))
            if not key or not value or confidence < min_confidence:
                continue  # conservative: skip weak/empty facts
            await upsert_fact(
                s, project_id=project_id, key=key, value=value,
                confidence=confidence, scope=f.get("scope", "project"),
            )
            stored.append({"key": key, "value": value, "confidence": confidence})
    return stored
