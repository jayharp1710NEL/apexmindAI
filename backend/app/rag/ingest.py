"""Document ingestion: persist a document, chunk it, embed chunks, store vectors."""

from __future__ import annotations

import uuid

from app.config import settings
from app.db.models import DocChunk, Document
from app.rag.chunker import chunk_text


async def ingest_document(
    *,
    llm,
    session_factory,
    project_id: uuid.UUID,
    filename: str,
    content: str,
    content_type: str | None = None,
) -> dict:
    chunks = chunk_text(
        content,
        size_tokens=settings.chunk_size_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
    )
    if not chunks:
        # Still record the (empty) document for visibility.
        async with session_factory() as s, s.begin():
            doc = Document(project_id=project_id, filename=filename,
                           content_type=content_type, size_bytes=len(content))
            s.add(doc)
            await s.flush()
            doc_id = doc.id
        return {"document_id": str(doc_id), "chunks": 0}

    emb = await llm.embed(chunks)
    async with session_factory() as s, s.begin():
        doc = Document(project_id=project_id, filename=filename,
                       content_type=content_type, size_bytes=len(content))
        s.add(doc)
        await s.flush()
        for i, (text, vec) in enumerate(zip(chunks, emb.embeddings, strict=True)):
            s.add(DocChunk(document_id=doc.id, idx=i, content=text,
                           token_count=len(text.split()), embedding=vec))
        doc_id = doc.id
    return {"document_id": str(doc_id), "chunks": len(chunks)}
