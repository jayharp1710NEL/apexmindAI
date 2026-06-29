"""Orchestrator routes: start a run and stream plan/step/answer events over WS."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.chat import repository as repo

router = APIRouter()


class StartRunIn(BaseModel):
    goal: str
    session_id: uuid.UUID | None = None


@router.post("/api/runs")
async def start_run(body: StartRunIn, request: Request) -> dict:
    """Start an orchestrated run in the background; returns a job id to poll."""
    factory = request.app.state.session_factory
    orchestrator = request.app.state.orchestrator
    jobs = request.app.state.run_jobs

    session_id = body.session_id
    if session_id is None:
        user_id, project_id = await repo.get_or_create_default_context(factory)
        async with factory() as s, s.begin():
            sess = await repo.create_session(
                s, project_id=project_id, user_id=user_id, title="API run"
            )
            session_id = sess.id

    job = jobs.create(goal=body.goal, session_id=str(session_id))

    async def _runner() -> None:
        async def emit(ev: dict) -> None:
            job.apply(ev)
        try:
            await orchestrator.run(goal=body.goal, session_id=str(session_id),
                                   emit=emit)
            if job.status == "running":
                job.status = "completed"
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"

    asyncio.create_task(_runner())
    return {"job_id": job.id, "session_id": str(session_id), "status": "running"}


@router.get("/api/runs/{job_id}")
async def get_run(job_id: str, request: Request) -> dict:
    job = request.app.state.run_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "run job not found")
    return job.to_dict()


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
