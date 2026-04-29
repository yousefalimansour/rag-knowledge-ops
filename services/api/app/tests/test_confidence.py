from uuid import uuid4

from app.retrieval.confidence import REFUSAL_THRESHOLD, is_refusal, score
from app.retrieval.types import RetrievalCandidate


def _cand(*, doc_id=None, rerank=None, fused=None) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid4(),
        document_id=doc_id or uuid4(),
        title="t",
        text="x",
        source_type="md",
        heading=None,
        page_number=None,
        chunk_index=0,
        score=fused or 0.0,
        rerank_score=rerank,
    )


def test_empty_input_yields_zero_confidence_and_refusal():
    b = score([])
    assert b.composite == 0.0
    assert is_refusal(b)


def test_single_strong_chunk_passes_threshold():
    b = score([_cand(rerank=0.95)])
    assert b.composite >= REFUSAL_THRESHOLD


def test_three_diverse_strong_chunks_high_confidence():
    cs = [_cand(rerank=0.95), _cand(rerank=0.9), _cand(rerank=0.85)]
    b = score(cs)
    assert b.diversity == 1.0
    assert b.evidence_count == 1.0
    assert b.composite > 0.7


def test_clustered_chunks_have_lower_diversity():
    same_doc = uuid4()
    cs = [_cand(doc_id=same_doc, rerank=0.9) for _ in range(3)]
    b = score(cs)
    assert b.diversity < 0.5


def test_low_top_score_triggers_refusal():
    cs = [_cand(rerank=0.10), _cand(rerank=0.05)]
    b = score(cs)
    assert is_refusal(b)


def test_uses_rerank_score_when_present_else_fused():
    cs = [_cand(rerank=0.9, fused=0.1), _cand(fused=0.8)]
    b = score(cs)
    # Top of these is 0.9 (rerank wins) — so top_score reflects that.
    assert b.top_score == 0.9
