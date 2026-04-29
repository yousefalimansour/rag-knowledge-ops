from uuid import uuid4

from app.retrieval.types import RetrievalCandidate
from app.services.citations import extract_cited_ids, validate_and_filter


def _cand() -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid4(),
        document_id=uuid4(),
        title="t",
        text="text body here.",
        source_type="md",
        heading=None,
        page_number=None,
        chunk_index=0,
    )


def test_extract_in_first_appearance_order():
    a, b = _cand(), _cand()
    answer = f"Claim one [{a.chunk_id}]. Claim two [{b.chunk_id}]. Claim one again [{a.chunk_id}]."
    ids = extract_cited_ids(answer)
    assert ids == [a.chunk_id, b.chunk_id]


def test_unknown_citation_is_dropped_from_answer():
    a = _cand()
    fake = uuid4()
    answer = f"Real fact [{a.chunk_id}]. Hallucination [{fake}]."
    clean, sources, info = validate_and_filter(answer, [a])
    assert str(fake) in info["dropped"]
    assert str(fake) not in clean
    assert [s.chunk_id for s in sources] == [a.chunk_id]


def test_combined_citations_handled():
    a, b = _cand(), _cand()
    answer = f"Multi [{a.chunk_id}][{b.chunk_id}]."
    _, sources, _ = validate_and_filter(answer, [a, b])
    assert {s.chunk_id for s in sources} == {a.chunk_id, b.chunk_id}


def test_no_citations_yields_empty_sources():
    a = _cand()
    clean, sources, _ = validate_and_filter("No cites here.", [a])
    assert clean == "No cites here."
    assert sources == []
