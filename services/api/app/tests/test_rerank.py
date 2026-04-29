from uuid import uuid4

from app.retrieval.rerank import _parse_scores, rerank
from app.retrieval.types import RetrievalCandidate


def _cand(score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid4(),
        document_id=uuid4(),
        title="t",
        text="some text",
        source_type="md",
        heading=None,
        page_number=None,
        chunk_index=0,
        score=score,
    )


def test_parse_scores_handles_nested_array():
    raw = '[{"id":"a","score":0.9},{"id":"b","score":0.1}]'
    out = _parse_scores(raw)
    assert out == [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.1}]


def test_parse_scores_clamps_to_zero_one():
    raw = '[{"id":"a","score":1.5},{"id":"b","score":-0.2}]'
    out = _parse_scores(raw)
    assert out[0]["score"] == 1.0
    assert out[1]["score"] == 0.0


def test_rerank_falls_back_on_llm_error(monkeypatch):
    from app.retrieval import rerank as rr

    def boom(*_a, **_k):
        from app.core.errors import LLMError

        raise LLMError("nope")

    monkeypatch.setattr(rr, "generate_text", boom)
    cands = [_cand(0.9), _cand(0.5), _cand(0.1)]
    out, used = rr.rerank("q", cands, top_k_in=10, top_k_out=3)
    assert used is False
    assert [c.chunk_id for c in out] == [c.chunk_id for c in cands]


def test_rerank_reorders_by_llm_scores(monkeypatch):
    from app.retrieval import rerank as rr

    cands = [_cand(0.9), _cand(0.5), _cand(0.1)]
    cid_a, cid_b, cid_c = (str(c.chunk_id) for c in cands)
    fake = f'[{{"id":"{cid_a}","score":0.1}},{{"id":"{cid_b}","score":0.95}},{{"id":"{cid_c}","score":0.4}}]'
    monkeypatch.setattr(rr, "generate_text", lambda *a, **k: fake)
    out, used = rr.rerank("q", cands, top_k_in=10, top_k_out=3)
    assert used is True
    # b > c > a after rerank
    assert str(out[0].chunk_id) == cid_b
    assert str(out[1].chunk_id) == cid_c
    assert str(out[2].chunk_id) == cid_a
