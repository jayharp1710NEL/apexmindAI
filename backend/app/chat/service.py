"""Chat turn handling: persist the user message, stream the assistant reply token
by token, then persist the full assistant message.

The streaming itself goes through `LLMInterface.stream(...)`, so model calls are
routed and audited exactly like any other call (Steps 3-4).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from app.chat import repository as repo
from app.router.interface import LLMInterface
from app.router.types import Message as LLMMessage

# A `send` callback pushes a JSON-serializable event to the client.
SendFn = Callable[[dict], Awaitable[None]]

# Roles we replay as model context (DB may also hold 'system'/'tool').
_CONTEXT_ROLES = {"user", "assistant"}


async def handle_turn(
    *,
    session_factory,
    llm: LLMInterface,
    session_id: uuid.UUID,
    content: str,
    task_type: str,
    send: SendFn,
) -> None:
    # 0) safety pre-screen — refuse clear harm before any model call
    from app.safety.incidents import log_incident
    from app.safety.prescreen import REFUSAL_MESSAGE, prescreen_request

    screen = prescreen_request(content)
    if screen.decision == "refuse":
        async with session_factory() as s, s.begin():
            await repo.add_message(s, session_id=session_id, role="user", content=content)
            refusal = await repo.add_message(
                s, session_id=session_id, role="assistant", content=REFUSAL_MESSAGE,
                meta={"refused": True, "category": screen.category},
            )
            refusal_id = str(refusal.id)
        await log_incident(session_factory, kind="refusal", severity="warning",
                           decision="refuse", session_id=session_id,
                           detail={"category": screen.category, "reason": screen.reason})
        await send({"type": "refusal", "category": screen.category,
                    "content": REFUSAL_MESSAGE})
        await send({"type": "done", "message_id": refusal_id})
        return
    if screen.injection_detected:
        await log_incident(session_factory, kind="injection_in_request",
                           severity="info", session_id=session_id,
                           detail={"flags": screen.flags})

    # 1) persist the user message
    async with session_factory() as s, s.begin():
        await repo.add_message(s, session_id=session_id, role="user", content=content)

    # 2) build model context from full history (includes the message just stored)
    async with session_factory() as s:
        session = await repo.get_session(s, session_id)
        history = await repo.get_messages(s, session_id)
    messages = [
        LLMMessage(role=m.role, content=m.content)
        for m in history
        if m.role in _CONTEXT_ROLES
    ]

    # 2b) inject relevant durable project facts as system context (read path)
    system = None
    if session is not None:
        from app.memory.facts import format_facts_for_prompt, get_facts_for_context

        facts = await get_facts_for_context(session_factory, session.project_id)
        system = format_facts_for_prompt(facts) or None

    # 3) stream the assistant reply
    await send({"type": "start"})
    chunks: list[str] = []
    try:
        async for delta in llm.stream(task_type, messages=messages, system=system):
            chunks.append(delta)
            await send({"type": "token", "content": delta})
    except Exception as exc:  # surface errors; never hide them
        await send({"type": "error", "detail": f"{type(exc).__name__}: {exc}"})
        return

    # 4) persist the full assistant message
    text = "".join(chunks)
    async with session_factory() as s, s.begin():
        msg = await repo.add_message(
            s, session_id=session_id, role="assistant", content=text
        )
        message_id = msg.id

    # 5) self-evaluation: attach a Critic scorecard; revise once if high risk.
    #    (the revised content + scorecard are persisted/emitted inside the helper)
    if hasattr(llm, "generate"):
        try:
            await _self_eval_and_attach(
                llm, session_factory, message_id, content, text, send
            )
        except Exception as exc:  # never let evaluation break the answer
            await send({"type": "scorecard_error", "detail": str(exc)})

    await send({"type": "done", "message_id": str(message_id)})


async def _self_eval_and_attach(
    llm, session_factory, message_id, question: str, draft: str, send: SendFn
) -> str:
    from app.agents.critic import self_evaluate

    async def _revise(prev: str, card) -> str:
        issues = "; ".join(card.issues) or "reduce unsupported claims"
        resp = await llm.generate(
            "reasoning",
            system="Revise the answer to fix the listed issues. Be accurate and do "
                   "not assert unsupported claims.",
            prompt=f"Question: {question}\n\nDraft: {prev}\n\nIssues: {issues}\n\n"
                   f"Return the improved answer only.",
            max_tokens=800, temperature=0.3,
        )
        return resp.text.strip()

    final_text, card = await self_evaluate(
        llm, question=question, draft=draft, revise=_revise
    )
    scorecard = card.model_dump()
    async with session_factory() as s, s.begin():
        await repo.update_message(
            s, message_id,
            content=final_text if card.revised else None,
            meta={"scorecard": scorecard},
        )
    if card.revised:
        await send({"type": "revised", "content": final_text, "scorecard": scorecard})
    await send({"type": "scorecard", "scorecard": scorecard})
    return final_text
