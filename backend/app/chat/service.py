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
        message_id = str(msg.id)

    await send({"type": "done", "message_id": message_id})
