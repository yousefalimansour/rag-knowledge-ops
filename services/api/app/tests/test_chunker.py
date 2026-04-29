from app.ingestion.chunker import chunk_document
from app.ingestion.types import ExtractedDocument, Section


def _doc(*sections: Section) -> ExtractedDocument:
    return ExtractedDocument(title="t", source_type="md", sections=list(sections))


def test_short_section_emits_single_chunk():
    doc = _doc(Section(text="A short paragraph.", heading="Intro"))
    out = chunk_document(doc, chunk_tokens=512, overlap_tokens=64)
    assert len(out) == 1
    assert out[0].heading == "Intro"
    assert out[0].chunk_index == 0


def test_oversize_text_splits_with_overlap():
    big = ". ".join(f"Sentence number {i} and some extra padding text" for i in range(200))
    doc = _doc(Section(text=big, heading="Body"))
    out = chunk_document(doc, chunk_tokens=64, overlap_tokens=8)
    assert len(out) >= 3
    # Sequential chunk indices.
    for i, c in enumerate(out):
        assert c.chunk_index == i
    # Sanity: every chunk carries the heading.
    assert all(c.heading == "Body" for c in out)
    # Char budget honored within a small slop.
    max_chars = 64 * 4
    overlap_chars = 8 * 4
    assert all(len(c.text) <= max_chars + overlap_chars for c in out)


def test_per_section_metadata_propagates():
    doc = _doc(
        Section(text="Page one stuff.", heading="A", page_number=1),
        Section(text="Page two stuff.", heading="B", page_number=2),
    )
    out = chunk_document(doc)
    headings = {c.heading for c in out}
    pages = {c.page_number for c in out}
    assert headings == {"A", "B"}
    assert pages == {1, 2}


def test_empty_section_skipped():
    doc = _doc(Section(text="", heading="Nope"), Section(text="Real text", heading="Yes"))
    out = chunk_document(doc)
    assert all(c.heading == "Yes" for c in out)
