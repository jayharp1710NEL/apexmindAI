"""Chat REST + WebSocket routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.chat import repository as repo
from app.chat import service
from app.chat.schemas import (
    CreateSessionIn,
    MessageOut,
    SessionOut,
    UserMessageIn,
)

router = APIRouter()


def _session_factory(app):
    return app.state.session_factory


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #
@router.post("/api/sessions", response_model=SessionOut)
async def create_session(body: CreateSessionIn, request: Request) -> SessionOut:
    factory = _session_factory(request.app)
    user_id, project_id = await repo.get_or_create_default_context(factory)
    async with factory() as s, s.begin():
        sess = await repo.create_session(
            s, project_id=project_id, user_id=user_id, title=body.title
        )
        return SessionOut(id=sess.id, title=sess.title, created_at=sess.created_at)


@router.get("/api/sessions", response_model=list[SessionOut])
async def list_sessions(request: Request) -> list[SessionOut]:
    factory = _session_factory(request.app)
    _, project_id = await repo.get_or_create_default_context(factory)
    async with factory() as s:
        sessions = await repo.list_sessions(s, project_id=project_id)
        return [
            SessionOut(id=x.id, title=x.title, created_at=x.created_at)
            for x in sessions
        ]


@router.get("/api/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(session_id: uuid.UUID, request: Request) -> list[MessageOut]:
    factory = _session_factory(request.app)
    async with factory() as s:
        if await repo.get_session(s, session_id) is None:
            raise HTTPException(status_code=404, detail="session not found")
        msgs = await repo.get_messages(s, session_id)
        return [
            MessageOut(
                id=m.id, role=m.role, content=m.content, meta=m.meta,
                created_at=m.created_at,
            )
            for m in msgs
        ]


# --------------------------------------------------------------------------- #
# WebSocket: streamed chat
# --------------------------------------------------------------------------- #
@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: uuid.UUID) -> None:
    await websocket.accept()
    factory = websocket.app.state.session_factory
    llm = websocket.app.state.llm

    # Validate the session exists before accepting turns.
    async with factory() as s:
        if await repo.get_session(s, session_id) is None:
            await websocket.send_json({"type": "error", "detail": "session not found"})
            await websocket.close()
            return

    async def send(event: dict) -> None:
        await websocket.send_json(event)

    try:
        while True:
            raw = await websocket.receive_json()
            try:
                msg = UserMessageIn.model_validate(raw)
            except ValidationError as exc:
                await send({"type": "error", "detail": f"invalid message: {exc}"})
                continue
            await service.handle_turn(
                session_factory=factory,
                llm=llm,
                session_id=session_id,
                content=msg.content,
                task_type=msg.task_type,
                send=send,
                model=msg.model,
                provider=msg.provider,
            )
    except WebSocketDisconnect:
        return
