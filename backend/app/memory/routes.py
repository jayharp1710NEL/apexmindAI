"""Memory API: list/delete project facts; run the extraction step over a session."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.chat import repository as repo
from app.memory import facts as facts_repo
from app.memory.memory_step import extract_and_store_facts

router = APIRouter(prefix="/api/memory", tags=["memory"])


class ExtractIn(BaseModel):
    session_id: uuid.UUID


@router.get("")
async def list_memory(request: Request) -> list[dict]:
    factory = request.app.state.session_factory
    _, project_id = await repo.get_or_create_default_context(factory)
    async with factory() as s:
        rows = await facts_repo.list_facts(s, project_id)
    return [
        {"id": str(f.id), "key": f.key, "value": f.value,
         "confidence": f.confidence, "scope": f.scope,
         "updated_at": f.updated_at.isoformat() if f.updated_at else None}
        for f in rows
    ]


@router.delete("/{fact_id}")
async def delete_memory(fact_id: uuid.UUID, request: Request) -> dict:
    factory = request.app.state.session_factory
    async with factory() as s, s.begin():
        ok = await facts_repo.delete_fact(s, fact_id)
    if not ok:
        raise HTTPException(404, "fact not found")
    return {"deleted": str(fact_id)}


@router.post("/extract")
async def extract_memory(body: ExtractIn, request: Request) -> dict:
    factory = request.app.state.session_factory
    async with factory() as s:
        session = await repo.get_session(s, body.session_id)
        if session is None:
            raise HTTPException(404, "session not found")
        project_id = session.project_id
        history = await repo.get_messages(s, body.session_id)
    stored = await extract_and_store_facts(
        llm=request.app.state.llm, session_factory=factory,
        project_id=project_id, conversation=history,
    )
    return {"stored": stored, "count": len(stored)}
