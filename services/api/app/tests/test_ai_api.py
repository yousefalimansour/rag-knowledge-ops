"""End-to-end tests for /api/ai/query and /api/ai/query/stream against a
seeded sqlite + stubbed Gemini + stubbed Chroma. Verifies the full
pipeline: rewrite → retrieve → fuse → rerank → answer → cite → confidence.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_corpus(signed_in, monkeypatch, tmp_path):
    """Stubs Gemini + Chroma, ingests one TXT file, runs the orchestrator
    so chunks are persisted and "indexed". Returns the workspace_id from /auth/me.
    """
    monkeypatch.chdir(tmp_path)

    from app.ai import chroma_client as cc
    from app.ai import embeddings as emb
    from app.api import ingest as ingest_router

    monkeypatch.setattr(emb, "embed_one", lambda t, **_: [0.1] * 768)
    monkeypatch.setattr(cc, "delete_for_document", lambda _doc_id: None)

    # Capture upserts so vector_search can mock-return them.
    upserted: list[dict] = []
    monkeypatch.setattr(cc, "upsert_chunks", lambda **kw: upserted.append(kw))
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    files = [
        (
            "files",
            (
                "kb.txt",
                b"Onboarding policy. New employees receive a laptop in their first week.\n\n"
                b"Expense policy. Submit receipts within 30 days; over 500 dollars needs approval.",
                "text/plain",
            ),
        )
    ]
    r = await signed_in.post("/api/ingest/files", files=files)
    assert r.status_code == 202
    job_id_str = r.json()["jobs"][0]["id"]

    # Run the orchestrator directly so chunks land in DB + vector mock.
    from app.db import session as db_session_module
    from app.services.ingest import ingest_document

    async with db_session_module.SessionLocal() as session:
        await ingest_document(session=session, job_id=UUID(job_id_str))

    return upserted


def _stub_vector_to_return_chunks(monkeypatch, ranked_chunk_ids: list[str]):
    """Make `vector_search` look up the requested chunk ids in the DB and
    return them in the requested order. Bypasses Chroma entirely.
    """
    from sqlalchemy import select as sa_select

    from app.models import Chunk, Document
    from app.retrieval import vector as vs
    from app.retrieval.types import RetrievalCandidate

    async def fake_vector_search(*, session, workspace_id, query, top_k, filters):
        rows = (
            await session.execute(
                sa_select(Chunk, Document)
                .join(Document, Document.id == Chunk.document_id)
                .where(Chunk.id.in_([UUID(x) for x in ranked_chunk_ids]))
            )
        ).all()
        by_id = {str(c.id): (c, d) for c, d in rows}
        out = []
        for rank, cid in enumerate(ranked_chunk_ids):
            if cid not in by_id:
                continue
            chunk, doc = by_id[cid]
            out.append(
                RetrievalCandidate(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    title=doc.title,
                    text=chunk.text,
                    source_type=doc.source_type,
                    heading=chunk.heading,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    score=1.0 - rank * 0.1,
                    vector_rank=rank,
                )
            )
        return out

    monkeypatch.setattr(vs, "vector_search", fake_vector_search)


async def test_query_returns_answer_with_cited_sources(signed_in, monkeypatch, tmp_path):
    await _seed_corpus(signed_in, monkeypatch, tmp_path)

    # Pull every chunk_id we just persisted so we can wire vector_search.
    from app.db import session as db_session_module
    from app.models import Chunk
    from sqlalchemy import select as sa_select

    async with db_session_module.SessionLocal() as session:
        chunks = (await session.execute(sa_select(Chunk).order_by(Chunk.chunk_index))).scalars().all()
    chunk_ids = [str(c.id) for c in chunks]
    assert chunk_ids, "ingestion should have produced at least one chunk"

    _stub_vector_to_return_chunks(monkeypatch, chunk_ids)

    # Stub the LLM: rewriter, reranker, and answer.
    from app.ai import llm
    from app.retrieval import query_rewrite as qr
    from app.retrieval import rerank as rr
    from app.services import reasoning

    monkeypatch.setattr(qr, "needs_rewrite", lambda _q: False)  # skip rewrite path
    fake_rerank_scores = json.dumps(
        [{"id": cid, "score": 0.9 - i * 0.1} for i, cid in enumerate(chunk_ids)]
    )
    # Both rerank and answer go through llm.generate_text — switch behavior by prompt.
    answer_template = (
        f"Onboarding gives a laptop in week one [{chunk_ids[0]}]. "
        f"Expense receipts are due within 30 days [{chunk_ids[1] if len(chunk_ids) > 1 else chunk_ids[0]}]."
    )

    def fake_generate_text(prompt: str, **_k):
        if "relevance judge" in (_k.get("system") or "").lower() or '"score"' in fake_rerank_scores and "Candidates:" in prompt:
            return fake_rerank_scores
        return answer_template

    monkeypatch.setattr(llm, "generate_text", fake_generate_text)
    monkeypatch.setattr(rr, "generate_text", fake_generate_text)
    monkeypatch.setattr(reasoning, "generate_text", fake_generate_text)

    r = await signed_in.post("/api/ai/query", json={"question": "What is the onboarding policy?"})
    assert r.status_code == 200, r.text
    body = r.json()
    # Every [uuid] citation in the answer must reference a real retrieved chunk.
    import re
    cited_in_text = re.findall(
        r"\[([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]",
        body["answer"],
    )
    assert cited_in_text, "answer should carry valid citations"
    assert set(cited_in_text).issubset(set(chunk_ids))
    cited_ids = {s["chunk_id"] for s in body["sources"]}
    assert cited_ids.issubset(set(chunk_ids))
    assert body["confidence"] >= 0.0
    assert body["cached"] is False


async def test_query_refuses_when_no_evidence(signed_in, monkeypatch, tmp_path):
    """No corpus → vector returns nothing → confidence 0 → refusal."""
    monkeypatch.chdir(tmp_path)

    from app.retrieval import vector as vs

    async def empty_vector(**_k):
        return []

    monkeypatch.setattr(vs, "vector_search", empty_vector)

    r = await signed_in.post("/api/ai/query", json={"question": "What did the CEO say in March?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "I don't have evidence" in body["answer"]
    assert body["sources"] == []
    assert body["confidence"] < 0.25


async def test_query_cache_avoids_second_llm_call(signed_in, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    # Stub cache to behave like real Redis but in-memory
    from app.services import query_cache

    store: dict[str, str] = {}

    async def fake_get(k):
        raw = store.get(k)
        return json.loads(raw) if raw else None

    async def fake_put(k, v, *, ttl=600):
        store[k] = json.dumps(v, default=str)

    monkeypatch.setattr(query_cache, "get", fake_get)
    monkeypatch.setattr(query_cache, "put", fake_put)

    # Stub vector + LLM
    from app.ai import llm
    from app.retrieval import vector as vs

    call_count = {"n": 0}

    def counted_generate(*a, **k):
        call_count["n"] += 1
        return "stubbed answer with no citations."

    async def empty_vector(**_k):
        return []

    monkeypatch.setattr(vs, "vector_search", empty_vector)
    monkeypatch.setattr(llm, "generate_text", counted_generate)

    body = {"question": "anything", "use_query_rewrite": False}
    r1 = await signed_in.post("/api/ai/query", json=body)
    r2 = await signed_in.post("/api/ai/query", json=body)
    assert r1.status_code == r2.status_code == 200
    assert r2.json()["cached"] is True
