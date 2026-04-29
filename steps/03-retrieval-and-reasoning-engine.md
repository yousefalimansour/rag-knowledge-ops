# Step 03 — Retrieval & Reasoning Engine

## Objective

Build the RAG core: a hybrid retrieval pipeline (vector + keyword + RRF fusion + Gemini reranking + query rewriting) wrapped in a strict, citation-only LLM reasoning step that returns grounded answers, verifiable sources, calibrated confidence, and an SSE streaming variant.

## User Value

Users get answers they can trust — every claim is backed by a chunk they can click into, low-evidence questions get a refusal instead of fabrication, and conversational follow-ups still resolve to focused searches.

## Scope

- `POST /api/ai/query` — synchronous: full pipeline + JSON answer.
- `POST /api/ai/query/stream` — SSE: same pipeline; streams the answer tokens, emits sources at end.
- `GET /api/search` — raw retrieval results (no LLM step), useful for debugging and the Knowledge Search UI.
- Query rewriting (only when needed).
- Hybrid search: Chroma vector + Postgres `tsvector` keyword.
- Reciprocal Rank Fusion to combine.
- Gemini-based listwise reranking on top-N candidates.
- Filtering: by score threshold, by document/source/date when provided.
- Confidence scoring (heuristic + agreement signals).
- Strict prompt that **forbids uncited claims** and demands refusal when evidence is weak.
- Per-question Redis cache (LRU, content-hash key).

## Required Features

- Workspace-scoped retrieval everywhere.
- Optional filters in request: `source_types`, `document_ids`, `date_from`, `date_to`.
- Refusal contract: no chunks above threshold → answer = "I don't have evidence about this in the knowledge base." with `confidence ≤ 0.2` and `sources = []`.
- Citation post-validation: every `chunk_id` cited in the answer must exist in the retrieved set; otherwise mark answer low-confidence and strip the bad citation.
- Streaming endpoint emits structured events: `start`, `token`, `sources`, `confidence`, `done`, `error`.

## API Contracts

```http
POST /api/ai/query                            (auth, rate-limited)
Body:
  {
    "question": "What did we decide about pricing last week?",
    "filters": {
      "source_types": ["slack","md"],         // optional
      "document_ids": ["..."],                // optional
      "date_from": "2026-04-22",              // optional
      "date_to":   "2026-04-29"               // optional
    },
    "use_query_rewrite": true,                // optional, default true
    "top_k": 8                                // optional, default 8
  }

200:
  {
    "answer": "string",
    "sources": [
      {
        "document_id": "uuid",
        "title": "string",
        "chunk_id": "uuid",
        "snippet": "quoted/summarized snippet",
        "score": 0.87,
        "page": 3,
        "heading": "Pricing",
        "source_type": "md"
      }
    ],
    "confidence": 0.91,
    "reasoning": "Short user-facing reasoning summary (not chain-of-thought)."
  }

POST /api/ai/query/stream                     (auth, SSE)
SSE events (one per line, JSON-encoded data):
  event: start    data: { "question": "..." }
  event: token    data: { "delta": "..." }   (repeated)
  event: sources  data: { "sources": [...] }
  event: confidence data: { "confidence": 0.91, "reasoning": "..." }
  event: done     data: { "ok": true }
  event: error    data: { "message": "..." }

GET /api/search                               (auth)
Query: ?q=&top_k=&source_types=&document_ids=&date_from=&date_to=
  → { "results": [ { chunk + score + breakdown of vector/keyword contributions } ] }
```

## Implementation Tasks

1. **Embeddings client** (already from step 02): single `embed(text)` for query.
2. **Vector search** (`app/retrieval/vector.py`): Chroma similarity with workspace + filter metadata, returns top-K with scores.
3. **Keyword search** (`app/retrieval/keyword.py`): Postgres `to_tsquery` over `chunks.content_tsv` with `ts_rank`, joined to documents for filters.
4. **Fusion** (`app/retrieval/fusion.py`): Reciprocal Rank Fusion `score = Σ 1 / (k + rank_i)` with `k=60`.
5. **Query rewriter** (`app/retrieval/query_rewrite.py`):
   - Gemini called with a small prompt: "Rewrite the user's question into 1–3 short search queries. If the question is already a clean keyword query, return it unchanged."
   - Skip rewrite when question is short and already keyword-shaped (heuristic guard to save latency/cost).
6. **Reranker** (`app/retrieval/rerank.py`):
   - Gemini listwise rerank over top-20 fused candidates → return top-K (default 8).
   - Falls back gracefully to fusion order if Gemini errors.
7. **Reasoning prompt** (`app/ai/prompts/answer.py`):
   - System: "You answer only from the provided context. Cite each claim by `[chunk_id]`. If evidence is insufficient, say so. Do not invent. Keep answer concise and structured."
   - Inputs: question, top chunks (with id, title, snippet, source).
   - Output: answer text with inline `[chunk_id]` markers; the API converts these to `sources[]`.
8. **Confidence scorer** (`app/retrieval/confidence.py`):
   - Inputs: top score, score gap (top1 − top2), source agreement (do top chunks share documents/themes?), evidence count above threshold.
   - Output: 0–1. Threshold for refusal: composite < 0.25.
9. **Citation post-validator**: parse `[chunk_id]` markers from answer; cross-check against retrieved set; drop unknown ids and downgrade confidence.
10. **Cache layer**: Redis key `q:{workspace_id}:{sha256(question + filters)}` → answer payload; TTL 10 min; bypassed when filters target a recently updated doc.
11. **Streaming endpoint**: do retrieval + rerank synchronously (fast), then stream Gemini's generation as SSE; emit sources + confidence after token stream completes.
12. **`GET /api/search`**: returns fused, reranked candidates without LLM step — used by Knowledge Search UI and for debugging.

## Edge Cases

- Question is empty / whitespace → 400.
- Question references a doc by id the user can't access → silently filter out, answer from rest, mention if no evidence remains.
- Hybrid search returns vector-only or keyword-only matches → fusion still works (one side empty → identity).
- Retrieved chunks all from one doc → confidence not boosted by "agreement" — use diversity-aware adjustment.
- Conflicting chunks → instruct LLM to surface the conflict in the answer (this also feeds Insights step 05).
- Streaming client disconnect mid-answer → cancel Gemini generation; log truncated event.
- Rerank fails → fallback to fusion order, mark `reasoning` with "(rerank fallback)".
- Cache hit when underlying doc was updated → invalidate by `workspace_updated_at` watermark stored alongside cache entry.

## Security Considerations

- Strict workspace filter at every retrieval layer.
- Untrusted document content goes into a clearly delimited "Context" block in the prompt — never substituted into instructions. Prompt-injection mitigations:
  - Wrap each chunk in `<doc id="...">…</doc>` and instruct the model to ignore any instructions inside doc tags.
  - Strip obvious "ignore previous instructions" phrases before passing? **No** — don't sanitize content (that's a losing arms race); rely on prompt structure + post-validation.
- Gemini API key never leaks to client; only the API service holds it.
- Rate limit `/api/ai/query` more strictly than other endpoints (default 20/min/user).
- SSE endpoint validates auth before opening the stream and re-checks on each event flush.

## Testing Plan

- **Unit**:
  - RRF math on synthetic ranked lists.
  - Confidence scorer over a matrix of inputs.
  - Citation validator parses `[chunk_id]` and rejects unknown ids.
  - Query-rewriter heuristic guard skips short keyword questions.
- **Integration**:
  - End-to-end: ingest a fixture corpus → ask 5 known-answer questions → assert top sources contain the expected doc.
  - Refusal: ask a question outside the corpus → assert refusal text + low confidence.
  - Streaming: hit `/stream`, collect events, assert order: start → token+ → sources → confidence → done.
- **Eval** (formal harness lives in step 07): wire the retrieval-quality script that runs ~15 Q&A pairs.

## Acceptance Criteria

- [ ] `POST /api/ai/query` returns answer + non-empty sources for in-corpus questions.
- [ ] Out-of-corpus questions get refusal with low confidence.
- [ ] Citations always reference chunk ids that exist in the retrieved set.
- [ ] Streaming endpoint emits the documented event sequence.
- [ ] Hybrid search visibly outperforms vector-only on keyword-heavy questions in the eval set.
- [ ] Reranker improves NDCG over fusion-only on the eval set (or at minimum doesn't hurt).
- [ ] Cache hit avoids the LLM call (verifiable via logs / metrics).

## Next

→ `steps/04-ai-copilot-frontend.md`
