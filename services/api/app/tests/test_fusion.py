from uuid import uuid4

from app.retrieval.fusion import rrf_fuse
from app.retrieval.types import RetrievalCandidate


def _cand(idx: int, *, vec_rank=None, kw_rank=None) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid4(),
        document_id=uuid4(),
        title=f"doc-{idx}",
        text=f"text-{idx}",
        source_type="md",
        heading=None,
        page_number=None,
        chunk_index=idx,
        vector_rank=vec_rank,
        keyword_rank=kw_rank,
    )


def test_single_list_orders_by_input_position():
    a, b, c = _cand(0, vec_rank=0), _cand(1, vec_rank=1), _cand(2, vec_rank=2)
    fused = rrf_fuse([a, b, c])
    assert [x.chunk_id for x in fused] == [a.chunk_id, b.chunk_id, c.chunk_id]
    # Standard RRF k=60 → first item has score 1/(60+1)
    assert abs(fused[0].score - (1 / 61)) < 1e-9


def test_overlapping_lists_combine_scores():
    a, b, c = _cand(0, vec_rank=0), _cand(1, vec_rank=1), _cand(2, vec_rank=2)
    # Same chunk_ids in second list with different ranks
    a2 = RetrievalCandidate(
        chunk_id=a.chunk_id,
        document_id=a.document_id,
        title=a.title,
        text=a.text,
        source_type=a.source_type,
        heading=None,
        page_number=None,
        chunk_index=a.chunk_index,
        keyword_rank=2,
    )
    fused = rrf_fuse([a, b, c], [c, b, a2])
    # Same set, different order. `a` is rank 0 in vec list, rank 2 in kw list.
    # `c` is rank 2 in vec list, rank 0 in kw list. Both should score the same.
    by_id = {x.chunk_id: x.score for x in fused}
    assert abs(by_id[a.chunk_id] - by_id[c.chunk_id]) < 1e-9
    # Carries both rank metadata after merge.
    a_after = next(x for x in fused if x.chunk_id == a.chunk_id)
    assert a_after.vector_rank == 0
    assert a_after.keyword_rank == 2


def test_one_empty_side_is_identity():
    a, b = _cand(0, vec_rank=0), _cand(1, vec_rank=1)
    only_left = rrf_fuse([a, b])
    with_empty_right = rrf_fuse([a, b], [])
    assert [x.chunk_id for x in only_left] == [x.chunk_id for x in with_empty_right]
