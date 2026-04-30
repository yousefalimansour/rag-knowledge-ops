from uuid import uuid4

from app.insights.dedup import dedup_hash


def test_hash_is_stable_across_id_order():
    a, b, c = uuid4(), uuid4(), uuid4()
    h1 = dedup_hash(type_="conflict", source_chunk_ids=[a, b, c], title="Two policies disagree")
    h2 = dedup_hash(type_="conflict", source_chunk_ids=[c, a, b], title="Two policies disagree")
    assert h1 == h2


def test_hash_is_stable_across_title_whitespace_and_case():
    a, b = uuid4(), uuid4()
    h1 = dedup_hash(type_="conflict", source_chunk_ids=[a, b], title="Policy Conflict on Pricing")
    h2 = dedup_hash(type_="conflict", source_chunk_ids=[a, b], title="  policy conflict  on pricing  ")
    assert h1 == h2


def test_hash_changes_with_type():
    a, b = uuid4(), uuid4()
    assert dedup_hash(type_="conflict", source_chunk_ids=[a, b], title="t") != dedup_hash(
        type_="repeated_decision", source_chunk_ids=[a, b], title="t"
    )


def test_hash_changes_with_different_ids():
    a, b, c = uuid4(), uuid4(), uuid4()
    assert dedup_hash(type_="conflict", source_chunk_ids=[a, b], title="t") != dedup_hash(
        type_="conflict", source_chunk_ids=[a, c], title="t"
    )
