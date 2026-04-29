from app.ingestion.extractors.markdown import extract_markdown
from app.ingestion.extractors.notion import extract_notion
from app.ingestion.extractors.slack import extract_slack
from app.ingestion.extractors.text import extract_txt


def test_text_extractor_paragraphs():
    raw = b"first paragraph.\n\nsecond paragraph.\n\nthird."
    doc = extract_txt(raw=raw, title="t.txt")
    assert doc.source_type == "txt"
    assert len(doc.sections) == 3
    assert doc.sections[0].text == "first paragraph."


def test_markdown_extractor_preserves_headings():
    raw = b"# Top\nintro line\n\n## Sub one\nbody one\n\n## Sub two\nbody two"
    doc = extract_markdown(raw=raw, title="t.md")
    headings = [s.heading for s in doc.sections]
    assert "Top" in headings and "Sub one" in headings and "Sub two" in headings


def test_markdown_extractor_no_headings_returns_body_section():
    """No headings → one heading-less section. Chunker subdivides at sentence
    boundaries, which is the actual fallback behavior the brief asks for."""
    raw = b"para one.\n\npara two."
    doc = extract_markdown(raw=raw, title="t.md")
    assert all(s.heading is None for s in doc.sections)
    assert len(doc.sections) == 1
    assert "para one" in doc.sections[0].text and "para two" in doc.sections[0].text


def test_slack_extractor_groups_by_thread_and_orders_by_ts():
    payload = {
        "channel": "general",
        "messages": [
            {"user": "alice", "ts": "1717084800.000100", "text": "hello"},
            {"user": "bob", "ts": "1717084810.000000", "text": "reply 1", "thread_ts": "1717084800.000100"},
            {"user": "alice", "ts": "1717084820.000000", "text": "reply 2", "thread_ts": "1717084800.000100"},
            {"user": "carol", "ts": "1717084900.000000", "text": "new top-level"},
        ],
    }
    doc = extract_slack(payload=payload, title="thread")
    assert doc.source_type == "slack"
    # Two threads.
    assert len(doc.sections) == 2
    first = doc.sections[0]
    # Thread is in chronological order.
    assert first.text.index("hello") < first.text.index("reply 1") < first.text.index("reply 2")
    assert first.source_timestamp is not None


def test_notion_extractor_walks_blocks_with_headings():
    payload = {
        "title": "Page",
        "blocks": [
            {"type": "heading_1", "text": "Top"},
            {"type": "paragraph", "text": "intro line"},
            {"type": "heading_2", "text": "Sub"},
            {"type": "bulleted_list_item", "text": "alpha"},
            {"type": "bulleted_list_item", "text": "beta"},
        ],
    }
    doc = extract_notion(payload=payload, title="fallback")
    assert doc.title == "Page"
    headings = [s.heading for s in doc.sections]
    assert "Top" in headings and "Sub" in headings
    sub = next(s for s in doc.sections if s.heading == "Sub")
    assert "alpha" in sub.text and "beta" in sub.text
