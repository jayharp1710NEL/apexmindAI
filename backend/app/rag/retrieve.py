"""Vector retrieval over a project's chunks using pgvector cosine distance."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.db.models import DocChunk, Document


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    content: str
    distance: float  # cosine distance in [0, 2]; lower = more similar


async def retrieve(
    *,
    llm,
    session_factory,
    project_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    emb = await llm.embed([query])
    qvec = emb.embeddings[0]
    dist = DocChunk.embedding.cosine_distance(qvec).label("dist")
    stmt = (
        select(DocChunk.id, DocChunk.document_id, DocChunk.content, dist)
        .join(Document, DocChunk.document_id == Document.id)
        .where(Document.project_id == project_id)
        .where(DocChunk.embedding.isnot(None))
        .order_by(dist)
        .limit(top_k)
    )
    async with session_factory() as s:
        rows = (await s.execute(stmt)).all()
    return [
        RetrievedChunk(
            chunk_id=str(r.id), document_id=str(r.document_id),
            content=r.content, distance=float(r.dist),
        )
        for r in rows
    ]
