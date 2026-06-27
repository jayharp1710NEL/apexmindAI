"""Orchestrator routes: start a run and stream plan/step/answer events over WS."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.chat import repository as repo

router = APIRouter()


@router.websocket("/ws/run/{session_id}")
async def ws_run(websocket: WebSocket, session_id: uuid.UUID) -> None:
    await websocket.accept()
    factory = websocket.app.state.session_factory
    orchestrator = websocket.app.state.orchestrator

    async with factory() as s:
        if await repo.get_session(s, session_id) is None:
            await websocket.send_json({"type": "error", "detail": "session not found"})
            await websocket.close()
            return

    async def emit(event: dict) -> None:
        await websocket.send_json(event)

    try:
        while True:
            raw = await websocket.receive_json()
            goal = (raw or {}).get("goal", "").strip()
            if not goal:
                await emit({"type": "error", "detail": "missing 'goal'"})
                continue
            # Persist the goal as a user message for continuity with chat history.
            async with factory() as s, s.begin():
                await repo.add_message(
                    s, session_id=session_id, role="user", content=goal
                )
            await orchestrator.run(
                goal=goal, session_id=str(session_id), emit=emit
            )
    except WebSocketDisconnect:
        return
