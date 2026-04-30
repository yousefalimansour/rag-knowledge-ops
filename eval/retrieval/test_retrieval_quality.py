"""Retrieval-quality eval — parametrized over `questions.yaml`.

Runs in two layers so we don't blow the Gemini free-tier daily quota:

1. **Retrieval layer (cheap, runs on every question).** Embed query →
   vector + keyword search → fuse. Skip the LLM rewriter and the LLM
   reranker. This produces recall@5 and MRR — the core retrieval metrics
   that need no Gemini generation.

2. **Reasoning probe layer (expensive, budgeted).** For up to
   ``N_IN_CORPUS_PROBES`` in-corpus questions and up to
   ``N_REFUSAL_PROBES`` must-refuse questions, also call
   ``answer_question`` to verify (a) cited answers contain expected phrases
   and (b) the LLM-driven refusal contract holds end-to-end. Refusal can
   only be tested through the LLM because the prod system delegates the
   "do I have enough evidence?" decision to Gemini's answer prompt — the
   composite confidence score is necessary but not sufficient.

   If Gemini quota is exhausted partway through, the harness records
   "probe-skipped" rather than failing the run, and metrics that depend
   on probes are marked "(not measured)" rather than asserted.

Aggregate thresholds (only asserted on metrics that were actually measured):
    recall@5 >= 0.80                  (always asserted)
    mrr >= 0.60                       (always asserted)
    correct_refusal_rate >= 0.90      (asserted iff >=1 refusal probe ran)
    expected_phrase_rate >= 0.80      (asserted iff >=1 in-corpus probe ran)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.ai.prompts.answer import REFUSAL_TEXT
from app.core.errors import LLMError
from app.db.session import SessionLocal
from app.retrieval.confidence import is_refusal, score
from app.services.reasoning import answer_question
from app.services.retrieval import retrieve

# `conftest.py` sits next to this file; pytest puts it on sys.path automatically.
from conftest import EvalCorpus, load_questions  # type: ignore[import-not-found]

log = logging.getLogger("eval.retrieval")

RECALL_K = 5
N_IN_CORPUS_PROBES = 3
N_REFUSAL_PROBES = 3
THRESHOLDS = {
    "recall@5": 0.80,
    "mrr": 0.60,
    "correct_refusal_rate": 0.90,
    "expected_phrase_rate": 0.80,
}

QUESTIONS = load_questions()


@dataclass(slots=True)
class QuestionResult:
    qid: str
    question: str
    must_refuse: bool
    expected_doc_logical: list[str]
    retrieved_doc_logical: list[str]
    confidence: float
    rank_of_first_expected: int | None  # 1-indexed; None if none of expected hit
    retrieval_correct: bool  # in-corpus: expected in top-K. must-refuse: n/a (always True).
    # Reasoning-probe results (only populated when the LLM probe ran):
    probe_ran: bool = False
    probe_skipped_reason: str | None = None
    answer: str | None = None
    expected_phrases: list[str] = field(default_factory=list)
    phrases_present: list[bool] = field(default_factory=list)
    refused_by_llm: bool | None = None  # only meaningful when probe_ran


@dataclass(slots=True)
class Report:
    rows: list[QuestionResult] = field(default_factory=list)

    def metrics(self) -> dict[str, float]:
        non_refusal = [r for r in self.rows if not r.must_refuse]
        refusal_only = [r for r in self.rows if r.must_refuse]
        in_corpus_probed = [r for r in non_refusal if r.probe_ran and r.expected_phrases]
        refusal_probed = [r for r in refusal_only if r.probe_ran]

        recall_at_k = (
            sum(
                1
                for r in non_refusal
                if r.rank_of_first_expected is not None and r.rank_of_first_expected <= RECALL_K
            )
            / len(non_refusal)
            if non_refusal
            else 0.0
        )
        mrr = (
            sum(
                (1.0 / r.rank_of_first_expected) if r.rank_of_first_expected else 0.0
                for r in non_refusal
            )
            / len(non_refusal)
            if non_refusal
            else 0.0
        )
        phrase_rate = (
            sum(sum(r.phrases_present) / len(r.phrases_present) for r in in_corpus_probed)
            / len(in_corpus_probed)
            if in_corpus_probed
            else float("nan")
        )
        correct_refusal_rate = (
            sum(1 for r in refusal_probed if r.refused_by_llm) / len(refusal_probed)
            if refusal_probed
            else float("nan")
        )

        return {
            "recall@5": round(recall_at_k, 3),
            "mrr": round(mrr, 3),
            "expected_phrase_rate": round(phrase_rate, 3) if in_corpus_probed else float("nan"),
            "correct_refusal_rate": (
                round(correct_refusal_rate, 3) if refusal_probed else float("nan")
            ),
            "n_questions": float(len(self.rows)),
            "n_in_corpus": float(len(non_refusal)),
            "n_must_refuse": float(len(refusal_only)),
            "n_in_corpus_probes": float(len(in_corpus_probed)),
            "n_refusal_probes": float(len(refusal_probed)),
        }


@pytest.fixture(scope="session")
def report() -> Report:
    return Report()


@pytest.fixture(scope="session")
def probe_budget() -> dict[str, Any]:
    """Tracks remaining LLM probes per question class. Once Gemini quota
    raises an LLMError we flip `quota_exhausted` so the rest of the run
    skips probes without burning more retries."""
    return {
        "in_corpus_remaining": N_IN_CORPUS_PROBES,
        "refusal_remaining": N_REFUSAL_PROBES,
        "quota_exhausted": False,
    }


@pytest.mark.eval
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("q", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
async def test_retrieval_quality_per_question(
    q: dict[str, Any],
    corpus: EvalCorpus,
    report: Report,
    probe_budget: dict[str, Any],
) -> None:
    expected_logical: list[str] = list(q["expected_doc_ids"])
    expected_doc_uuids = {corpus.doc_id_for(logical) for logical in expected_logical}

    async with SessionLocal() as session:
        candidates, _debug = await retrieve(
            session=session,
            workspace_id=corpus.workspace_id,
            question=q["question"],
            top_k=RECALL_K,
            candidate_pool=20,
            use_query_rewrite=False,
            use_rerank=False,
        )

    confidence = score(candidates)

    retrieved_logical: list[str] = []
    rank_of_first_expected: int | None = None
    for rank, c in enumerate(candidates, start=1):
        logical = _logical_id_for(corpus, c.document_id)
        retrieved_logical.append(logical or f"<unknown:{c.document_id}>")
        if c.document_id in expected_doc_uuids and rank_of_first_expected is None:
            rank_of_first_expected = rank

    if q["must_refuse"]:
        retrieval_correct = True  # there's nothing right or wrong about retrieval here
    else:
        retrieval_correct = bool(
            rank_of_first_expected is not None and rank_of_first_expected <= RECALL_K
        )

    row = QuestionResult(
        qid=q["id"],
        question=q["question"],
        must_refuse=bool(q["must_refuse"]),
        expected_doc_logical=expected_logical,
        retrieved_doc_logical=retrieved_logical,
        confidence=float(confidence.composite),
        rank_of_first_expected=rank_of_first_expected,
        retrieval_correct=retrieval_correct,
    )

    expected_phrases: list[str] = list(q.get("expected_phrases", []))

    # Decide whether to run the LLM probe on this question.
    should_probe = False
    if not probe_budget["quota_exhausted"]:
        if q["must_refuse"] and probe_budget["refusal_remaining"] > 0:
            should_probe = True
            probe_budget["refusal_remaining"] -= 1
        elif (
            not q["must_refuse"]
            and expected_phrases
            and probe_budget["in_corpus_remaining"] > 0
        ):
            should_probe = True
            probe_budget["in_corpus_remaining"] -= 1

    if should_probe:
        try:
            async with SessionLocal() as session:
                ans = await answer_question(
                    session=session,
                    workspace_id=corpus.workspace_id,
                    question=q["question"],
                    top_k=RECALL_K,
                )
            row.probe_ran = True
            row.answer = ans.answer
            answer_text = ans.answer or ""
            # The system refuses if the answer text starts with the canonical
            # refusal sentence OR the LLM returned no validated sources.
            refusal_prefix = REFUSAL_TEXT.split(".", 1)[0]
            row.refused_by_llm = (
                answer_text.strip().startswith(refusal_prefix) or len(ans.sources) == 0
            )
            row.expected_phrases = expected_phrases
            row.phrases_present = [
                p.lower() in answer_text.lower() for p in expected_phrases
            ]
        except LLMError as e:
            probe_budget["quota_exhausted"] = True
            row.probe_skipped_reason = f"LLM unavailable: {str(e)[:80]}"
            log.warning("eval.probe.llm_unavailable", extra={"qid": q["id"]})

    report.rows.append(row)

    # Per-question hard fails. Retrieval is always asserted; the LLM-driven
    # refusal contract is asserted only when the probe ran (otherwise the
    # quota outage would mask a real regression).
    if not q["must_refuse"] and rank_of_first_expected is None:
        pytest.fail(
            f"[{q['id']}] none of expected docs {expected_logical} appeared in top-{RECALL_K}. "
            f"Retrieved: {retrieved_logical}",
            pytrace=False,
        )
    if q["must_refuse"] and row.probe_ran and not row.refused_by_llm:
        pytest.fail(
            f"[{q['id']}] expected the answer pipeline to refuse but it produced an answer "
            f"with {len(ans.sources)} sources (confidence={confidence.composite:.2f}).",
            pytrace=False,
        )


def test_aggregate_metrics_meet_thresholds(report: Report) -> None:
    """Always print the metric table — even when every per-question test
    passed — so reviewers see the numbers. Threshold assertions skip metrics
    that came back NaN (no probes ran, e.g. quota exhausted)."""
    if not report.rows:
        pytest.skip("Eval was skipped (likely no GOOGLE_API_KEY).")

    metrics = report.metrics()
    _print_report(report, metrics)

    failures: list[str] = []
    for k, threshold in THRESHOLDS.items():
        actual = metrics[k]
        if isinstance(actual, float) and actual != actual:
            continue  # NaN — metric was not measured this run
        if actual < threshold:
            failures.append(f"{k}={actual:.3f} (threshold {threshold:.2f})")
    if failures:
        pytest.fail("Eval thresholds not met:\n  - " + "\n  - ".join(failures), pytrace=False)


def _logical_id_for(corpus: EvalCorpus, document_id) -> str | None:
    for logical, doc_uuid in corpus.doc_id_by_logical.items():
        if doc_uuid == document_id:
            return logical
    return None


def _print_report(report: Report, metrics: dict[str, float]) -> None:
    line = "-" * 100
    print()
    print("=" * 100)
    print("RETRIEVAL-QUALITY EVAL — per-question outcome")
    print("=" * 100)
    print(line)
    print(
        f"{'qid':<6} {'kind':<14} {'rank':<5} {'conf':<6} {'probe':<10} "
        f"{'refused?':<10} {'phrases':<10} {'retr':<5} question"
    )
    print(line)
    for r in report.rows:
        kind = "must-refuse" if r.must_refuse else "in-corpus"
        rank = "-" if r.rank_of_first_expected is None else str(r.rank_of_first_expected)
        if r.probe_ran:
            probe = "ran"
            refused = "yes" if r.refused_by_llm else "no"
        elif r.probe_skipped_reason:
            probe = "skip(quota)"
            refused = "n/a"
        else:
            probe = "n/a"
            refused = "n/a"
        if r.probe_ran and r.expected_phrases:
            present = sum(r.phrases_present)
            phrases = f"{present}/{len(r.expected_phrases)}"
        else:
            phrases = "n/a"
        ok = "OK" if r.retrieval_correct else "FAIL"
        q_short = r.question if len(r.question) <= 50 else r.question[:47] + "..."
        print(
            f"{r.qid:<6} {kind:<14} {rank:<5} {r.confidence:<6.2f} {probe:<10} "
            f"{refused:<10} {phrases:<10} {ok:<5} {q_short}"
        )
    print(line)
    print()
    print("AGGREGATE METRICS")
    for k, v in metrics.items():
        threshold = THRESHOLDS.get(k)
        marker = ""
        if threshold is not None and isinstance(v, float) and v == v:
            marker = "  PASS" if v >= threshold else f"  FAIL (need >= {threshold})"
        elif threshold is not None and isinstance(v, float) and v != v:
            marker = "  (not measured — Gemini probe skipped)"
        print(f"  {k:<32} {v}{marker}")
    print("=" * 100)
