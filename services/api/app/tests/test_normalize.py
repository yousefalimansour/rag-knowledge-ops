from app.ingestion.normalize import normalize_text


def test_nfkc_unifies_compatibility_chars():
    # ﬁ (U+FB01 ligature) → 'fi'
    assert normalize_text("ﬁnal") == "final"


def test_strips_control_chars_but_keeps_whitespace():
    s = "hello\x00\x01world\nnext line\tindented"
    assert normalize_text(s) == "helloworld\nnext line\tindented"


def test_collapses_multi_blank_lines():
    s = "a\n\n\n\n\nb"
    assert normalize_text(s) == "a\n\nb"


def test_normalises_crlf():
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"


def test_idempotent():
    s = "Some text with\xa0nbsp\n\n\n\nmultiple blanks"
    assert normalize_text(normalize_text(s)) == normalize_text(s)
