"""RAG-lite tests against Postgres + pgvector with deterministic fake embeddings.

Proves: ingest stores chunks with vectors; retrieval finds the relevant chunk;
grounded answers carry [n]->chunk_id citations; and an unsupported query yields
"Unverified" WITHOUT calling the generator.
"""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.chat import repository as repo
from app.db.models import EMBED_DIM
from app.rag.answer import answer_question
from app.rag.ingest import ingest_document
from app.rag.retrieve import retrieve
from app.router.types import EmbedResponse, LLMResponse, Usage

TEST_DB = os.environ.get("APEX_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DB, reason="set APEX_TEST_DATABASE_URL to run RAG tests"
)


def _vec(textval: str) -> list[float]:
    """Deterministic bag-of-words vector: cosine reflects token overlap."""
    v = [0.0] * EMBED_DIM
    for w in set(textval.lower().split()):
        idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % EMBED_DIM
        v[idx] = 1.0
    return v


class FakeRagLLM:
    def __init__(self) -> None:
        self.generate_calls = 0

    async def embed(self, inputs, task_type=None) -> EmbedResponse:
        return EmbedResponse(embeddings=[_vec(t) for t in inputs],
                             model="fake-embed", provider="fake")

    async def generate(self, task_type, *, messages=None, system=None, prompt=None,
                       max_tokens=600, temperature=0.2, json_mode=False, stop=None):
        self.generate_calls += 1
        # Always answer with a [1] citation when invoked.
        return LLMResponse(text="The sky is blue [1].", model="m", provider="fake",
                           usage=Usage())


@pytest.fixture()
async def factory():
    engine = create_async_engine(TEST_DB)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM documents"))  # cascades to doc_chunks
    yield f
    await engine.dispose()


async def _project(factory):
    _, project_id = await repo.get_or_create_default_context(factory)
    return project_id


async def test_ingest_stores_chunks_with_vectors(factory):
    pid = await _project(factory)
    llm = FakeRagLLM()
    out = await ingest_document(
        llm=llm, session_factory=factory, project_id=pid,
        filename="d.txt", content="the sky is blue and clear today",
    )
    assert out["chunks"] >= 1
    async with factory() as s:
        n = await s.scalar(text("SELECT count(*) FROM doc_chunks WHERE embedding IS NOT NULL"))
    assert n >= 1


async def test_retrieve_finds_relevant_chunk(factory):
    pid = await _project(factory)
    llm = FakeRagLLM()
    await ingest_document(llm=llm, session_factory=factory, project_id=pid,
                          filename="sky.txt", content="the sky is blue")
    await ingest_document(llm=llm, session_factory=factory, project_id=pid,
                          filename="fruit.txt", content="apples and bananas are tasty")
    hits = await retrieve(llm=llm, session_factory=factory, project_id=pid,
                          query="what color is the sky", top_k=2)
    assert hits
    assert "sky" in hits[0].content  # most similar chunk is the sky one


async def test_answer_cites_chunks_when_supported(factory):
    pid = await _project(factory)
    llm = FakeRagLLM()
    await ingest_document(llm=llm, session_factory=factory, project_id=pid,
                          filename="sky.txt", content="the sky is blue")
    res = await answer_question(llm=llm, session_factory=factory, project_id=pid,
                                query="what color is the sky")
    assert res["grounded"] is True
    assert "[1]" in res["answer"]
    assert res["citations"] and res["citations"][0]["n"] == 1
    assert uuid.UUID(res["citations"][0]["chunk_id"])  # real chunk id


async def test_unsupported_query_is_unverified_without_calling_model(factory):
    pid = await _project(factory)
    llm = FakeRagLLM()
    await ingest_document(llm=llm, session_factory=factory, project_id=pid,
                          filename="fruit.txt", content="apples and bananas are tasty")
    res = await answer_question(llm=llm, session_factory=factory, project_id=pid,
                                query="quantum chromodynamics lagrangian symmetry")
    assert res["answer"] == "Unverified"
    assert res["citations"] == []
    assert llm.generate_calls == 0  # never fabricated an answer
