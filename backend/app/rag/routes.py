"""RAG REST routes: upload/list documents, ask grounded questions."""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.chat import repository as repo
from app.config import settings
from app.db.models import Document
from app.rag.answer import answer_question
from app.rag.ingest import ingest_document

router = APIRouter(prefix="/api", tags=["rag"])


class QueryIn(BaseModel):
    query: str


@router.post("/documents")
async def upload_document(
    request: Request, file: UploadFile = File(...)  # noqa: B008 — FastAPI idiom
) -> dict:
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("latin-1", "ignore")
    _, project_id = await repo.get_or_create_default_context(
        request.app.state.session_factory
    )
    return await ingest_document(
        llm=request.app.state.llm,
        session_factory=request.app.state.session_factory,
        project_id=project_id,
        filename=file.filename or "upload.txt",
        content=content,
        content_type=file.content_type,
    )


@router.get("/documents")
async def list_documents(request: Request) -> list[dict]:
    factory = request.app.state.session_factory
    _, project_id = await repo.get_or_create_default_context(factory)
    async with factory() as s:
        rows = (
            await s.scalars(
                select(Document)
                .where(Document.project_id == project_id)
                .order_by(Document.created_at.desc())
            )
        ).all()
    return [
        {"id": str(d.id), "filename": d.filename, "size_bytes": d.size_bytes,
         "created_at": d.created_at.isoformat()}
        for d in rows
    ]


@router.post("/rag/query")
async def rag_query(body: QueryIn, request: Request) -> dict:
    factory = request.app.state.session_factory
    _, project_id = await repo.get_or_create_default_context(factory)
    return await answer_question(
        llm=request.app.state.llm,
        session_factory=factory,
        project_id=project_id,
        query=body.query,
        top_k=settings.rag_top_k,
        max_distance=settings.rag_max_distance,
    )
