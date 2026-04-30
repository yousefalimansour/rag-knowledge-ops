from app.retrieval.query_rewrite import _parse_array, needs_rewrite, rewrite_query


def test_short_question_skips_rewrite():
    assert needs_rewrite("hi") is False
    assert needs_rewrite("pricing") is False


def test_keyword_query_skips_rewrite():
    # Three short words, no question/filler → keep as-is
    assert needs_rewrite("kops policy text") is False


def test_question_with_mark_triggers_rewrite():
    assert needs_rewrite("What is our refund policy?") is True


def test_filler_word_question_triggers_rewrite():
    assert needs_rewrite("how do new employees get a laptop") is True


def test_parse_array_handles_fenced_json():
    raw = '```json\n["a", "b", "c"]\n```'
    assert _parse_array(raw) == ["a", "b", "c"]


def test_parse_array_handles_plain_array():
    assert _parse_array('["x", "y"]') == ["x", "y"]


def test_parse_array_extracts_array_from_prose():
    raw = 'Sure! Here are the queries: ["alpha", "beta"]\nThat\'s all.'
    assert _parse_array(raw) == ["alpha", "beta"]


def test_parse_array_returns_empty_on_garbage():
    assert _parse_array("not json at all") == []


def test_rewrite_query_falls_back_when_llm_errors(monkeypatch):
    """When the LLM raises, rewrite must return only the original question
    rather than letting the exception bubble up."""
    from app.core.errors import LLMError
    from app.retrieval import query_rewrite as qr

    def boom(*_a, **_k):
        raise LLMError("no key")

    # Patch the rebinding inside `query_rewrite` (it does
    # `from app.ai.llm import generate_text`, so patching `llm.generate_text`
    # alone wouldn't reach the call site).
    monkeypatch.setattr(qr, "generate_text", boom)
    out = rewrite_query("How do new employees onboard their first week?")
    assert out == ["How do new employees onboard their first week?"]


def test_rewrite_query_combines_original_and_extras(monkeypatch):
    from app.retrieval import query_rewrite as qr

    monkeypatch.setattr(
        qr, "generate_text", lambda *a, **k: '["onboarding first week", "new hire week one"]'
    )
    out = qr.rewrite_query("How do new employees onboard their first week?")
    assert out[0] == "How do new employees onboard their first week?"
    assert "onboarding first week" in out
    assert len(out) <= 3
