# Session Memory — KnowledgeOps AI build

What this file is: a session-scoped scratchpad for the Claude Code agent. It
records what was actually shipped, the decisions taken, and the gotchas
caught during validation — so a future session can pick up without re-reading
the entire chat. The durable project context lives in `CLAUDE.md`; this is
working state, intentionally informal.

`.claude/` is gitignored except for `CLAUDE.md` itself.

---

## Sessions completed

**Step 00 — Project Understanding** ✅
- Added a "Reviewer Quick-Read" table to [steps/00-project-understanding.md](../steps/00-project-understanding.md) so the five gating questions (what / who / locked / out-of-scope / done) are answerable in under two minutes.

**Step 01 — Architecture & Setup** ✅
- Monorepo: `apps/web`, `services/api`, `services/worker`, `infra/docker`, `seed/`, root `package.json` + `pnpm-workspace.yaml` + `Makefile`.
- FastAPI skeleton with auth (signup/login/logout/me, Argon2 + JWT cookie + double-submit CSRF), `/api/health` deep-check, RFC 7807 errors, request-id middleware, JSON logging, Redis token-bucket rate limit, async SQLAlchemy 2.x + Alembic.
- Celery worker + beat skeletons sharing `app.*` from the api package via PYTHONPATH.
- Next.js 15 App Router with `(auth)` and `(app)` route groups, edge middleware redirecting unauth users to /login, TanStack Query, same-origin proxy via `next.config.mjs` for first-party cookies.
- Docker Compose with healthchecks (`db`, `cache`, `vector`, `api`), `worker`/`beat`/`web` gated on `service_healthy`, named volumes for pgdata/redisdata/chromadata.
- Tests: 8 backend pytest, 2 frontend vitest, all green.

**Step 02 — Ingestion Pipeline** ✅
- Migration 0002: `documents` (with unique `(workspace_id, content_hash)`), `chunks` (with `tsvector` GIN index on Postgres), `ingest_jobs`, `embedding_cache`.
- Five extractors: PDF (pypdf + pdfminer.six fallback), TXT, Markdown (heading-aware), Slack JSON (thread reassembly), Notion JSON (recursive blocks). MIME sniffing via `filetype`.
- Heading-aware chunker with sentence-boundary splits and overlap.
- Embedding service with per-text cache (`embedding_cache` table) keyed by SHA-256 + model name.
- Chroma upsert keyed by chunk_id with workspace_id metadata.
- Ingest orchestrator: extract → chunk → embed → index, idempotent on `ready`, replaces chunks on re-ingest.
- Celery task `worker.tasks.ingest.run` with autoretry × 3.
- Routers: `POST /api/ingest/files` (multipart), `POST /api/ingest/source` (JSON), `GET /api/docs` (filters + cursor), `GET /api/docs/:id`, `GET /api/jobs/:id`, `GET /api/jobs/stream/sse` (polling-based).
- Frontend: Documents list + detail, Upload page (file input + JSON paste), live SSE invalidation of the docs query.
- Tests: 33 backend (chunker, normalize, extractors, dedup, ingest API, jobs API, end-to-end ingest service with stubbed Gemini + Chroma).
- **Live validation passed**: `gemini-2.5-flash` + `gemini-embedding-001` with `output_dimensionality=768` produce `status=ready` in ~3 seconds per doc.

**Step 03 — Retrieval & Reasoning Engine** ✅
- Retrieval primitives: vector (Chroma cosine), keyword (Postgres `to_tsquery` + `ts_rank`, with SQLite fallback for tests), Reciprocal Rank Fusion (k=60).
- Query rewriter with heuristic guard (skip if short/keyword-shaped), Gemini-based listwise reranker on top-20 → top-K with graceful fallback to fusion order on LLM error.
- Confidence scorer: composite of top-similarity + score-gap + doc-diversity + evidence-count. Threshold 0.25 triggers refusal.
- Citation post-validator: parses `[uuid]` markers, drops citations not in retrieved set.
- Routers: `POST /api/ai/query` (Redis-cached, 10-min TTL), `POST /api/ai/query/stream` (SSE: start → token+ → sources → confidence → done), `GET /api/search` (raw retrieval, no LLM).
- Frontend: Copilot streaming chat with markdown answer rendering + numbered citation chips → SourcePreviewSheet, Knowledge Search with `<mark>` highlighting.
- Tests: 30 new (fusion math, confidence breakdown, citation extraction, query-rewrite parser, rerank fallback, end-to-end ai/query).
- **Live validation passed**: in-corpus question → confidence 0.77 + cited answer; out-of-corpus → refusal + confidence 0.0; cache-hit on 2nd identical query.

**Step 04 — AI Copilot Frontend** ✅
- UI primitives in `apps/web/components/ui/`: Sheet (Radix Dialog), Skeleton, Badge, Toast (with provider + `useToast`), StatusPill.
- App shell: Sidebar with `lucide-react` icons + active-state, Topbar with Radix DropdownMenu user menu and (placeholder) NotificationsBell.
- Polished screens: Dashboard with real counts + Quick-Ask deeplink to Copilot, Documents with filters + skeletons, Upload with drag-drop + per-row status + Slack/Notion JSON paste tab, Knowledge Search with match highlighting + Sheet preview, Copilot with `react-markdown` + numbered citation chips + refusal styling + welcome state, Settings page (profile + live `/api/health` panel + sign-out), Insights stub previewing the four planned types.
- Toast system used by Upload and Insights mutations.
- All 12 routes prerender. 7 protected routes return 200 when authed, 307 → /login otherwise.

**Step 05 — Proactive Intelligence Layer** ✅
- Migration 0003: `insights` (unique `dedup_hash`), `insight_runs`, `notifications`.
- Order-stable `dedup_hash = sha256(type + sorted chunk ids + normalized title)`.
- LLM generator for `conflict` + `repeated_decision` with strict per-type guards (≥2 distinct documents required).
- Deterministic `stale_document` scan (90-day cutoff).
- Generators: scoped (post-ingest, doc + similar peers), coordinator (watermark-based delta processing), nightly (full conflict + repeated + stale), manual.
- Beat schedules wired to real generators (replaced ping stubs).
- Notification dispatcher fans out to all workspace members for severity ≥ medium; also fires on ingest_completed / ingest_failed.
- Routers: `GET/PATCH /api/insights`, `POST /api/insights/run`, `GET /api/insights/runs`, `GET/PATCH /api/notifications`, `POST /api/notifications/mark-all-read`.
- Frontend: real Insights page (state filter + badges + evidence chips + dismiss/read/reopen), real NotificationsBell (unread badge + dropdown inbox + mark-all-read).
- Post-ingest hook in the ingest task fires both notification fan-out and scoped insight publish.
- Tests: 13 new (dedup hash stability, repo persistence, API filtering + state transitions, manual-run queueing, notification list/mark-read/mark-all-read).
- **Live validation passed**: 2 conflicting policy docs → conflict insight + high-severity notification visible within ~8 seconds. Gemini correctly identified the 1.5/10 vs 2.5/30 contradiction.

**Step 07 — Testing, Evaluation & Quality** ✅
- Added `test_rate_limit.py` (7 tests) and `test_insights_stale.py` (2 tests). **Backend now 94 pytest + 75.0% coverage.**
- Eval harness at `eval/retrieval/`: 5 corpus fixtures (pricing-v1+v2 with designed conflict, product-decisions, security-handbook, support-logs.json, onboarding.notion.json) + 15 Q&A in `questions.yaml`. Frugal-by-default (skips rewrite+rerank for retrieval-only questions, budgets 3 in-corpus + 3 must-refuse LLM probes).
- **Eval result with `gemini-3.1-flash-lite-preview`: recall@5=1.0, MRR=0.917, expected_phrase_rate=1.0, correct_refusal_rate=1.0** — all four thresholds asserted and met.
- Frontend tests: added `lib/highlight.test.tsx`, `lib/filters.test.ts`, `components/app/answer-renderer.test.tsx`. **13 frontend vitest passing (was 2).**
- Playwright e2e: 2 specs both green — `auth.spec.ts` (signup → dashboard → dropdown → sign out) and `copilot.spec.ts` (signup → upload → poll ready → ask → assert citation/grounded text + confidence pill). Copilot retries 5× on Gemini transient 503s with backoff, skips gracefully on sustained outage.
- Coverage wired: `make coverage` runs `pytest --cov` with `--cov-fail-under=70` against the `[tool.coverage.run|report]` config in `pyproject.toml`. Targeted modules where unit tests can reach the code (security, rate_limit, confidence, fusion, dedup, citations) are 93–100%; integration-only paths (vector.py, keyword.py postgres branch, pdf extractor) are exercised through the eval harness instead.
- Make targets: `test`, `test-api`, `test-web`, `eval`, `e2e`, `coverage`, `lint`, `lint-api`, `lint-web`, `typecheck`, `fmt`. `eval` propagates `GOOGLE_API_KEY` to the api container.
- `pyproject.toml` registers pytest markers (unit / integration / worker / eval). Eval has its own `pytest.ini` so it's runnable from any working dir.

**Bugs caught + fixed this step**
- `services.retrieval.retrieve` was sharing one `AsyncSession` across `asyncio.gather(vector_search, keyword_search)` — async SQLAlchemy forbids concurrent ops on one session. Serialized the calls; DB time is sub-ms next to LLM time anyway. Latent bug masked by unit tests that stub vector_search.
- `AnswerRenderer` placeholder `__CITE__id__` was being parsed as bold by ReactMarkdown. Switched to Unicode PUA sentinels ( / ).
- Vitest 2 doesn't auto-`cleanup()` Testing Library renders — added `vitest.setup.ts`.
- `app/insights/stale.py` did `datetime.now(UTC) - doc.updated_at` — raised `TypeError` on SQLite test backend (loses tz info). Added `_aware()` coercion.
- `test_query_rewrite.py` patched `llm.generate_text` but `query_rewrite` does `from app.ai.llm import generate_text`, so the patch was a no-op when `GOOGLE_API_KEY` is set. Switched to patching the rebinding inside `query_rewrite`.
- `test_settings.py` hardcoded `GEMINI_MODEL == "gemini-2.5-flash"` — broke when the user switched to flash-lite-preview. Now compares to `s.GEMINI_MODEL` (env-driven).
- Added `use_rerank` flag to `retrieve()` (default True) so the eval can opt out and save LLM calls.

**Final test count: 94 backend + 13 frontend + 16 eval + 2 e2e = 125 tests, all green.**

**Switched generation model 2026-04-30**: `gemini-2.5-flash` → `gemini-3.1-flash-lite-preview` (per user). Higher RPD, but transient 503 "experiencing high demand" is more frequent — handled with internal `google.api_core.retry` + test-side retries on the e2e.

**Step 06 — System Design & Infrastructure** ✅
- `Settings.safe_dump()` + custom `__repr__` redact `SECRET_KEY` / `JWT_SECRET` / `GOOGLE_API_KEY` / `DATABASE_URL` / `REDIS_URL`. Production fail-fast on placeholder values.
- New `app/core/publisher.py` — single Celery publish helper that attaches `request_id` to message headers; api never imports the worker package.
- Worker `setup_logging` signal installs JSON formatter (replacing Celery's plain-text default); `task_prerun` reads `request_id` from headers.
- New `app/core/cache.py` — `get_or_set(key, ttl, loader)` cache-aside with graceful Redis-outage fallback, `make_workspace_key` for tenant-isolated keys.
- `.env.example` rewritten with one comment per variable explaining purpose / default / prod gotchas.
- Seed script + 5 fixtures (`policies-old.md` + `policies-new.md` deliberately conflict; `security-handbook.md`; Slack pricing thread JSON; Notion onboarding JSON). Idempotent: re-runs reset the demo password and dedup by content_hash.
- Multi-stage api/worker Dockerfiles, non-root `kops` user at uid/gid 10001 (matched between images so the shared `uploads_data` volume works), uvicorn `--proxy-headers --forwarded-allow-ips=*`.
- `restart: unless-stopped` on every Compose service.
- `/docs` and `/openapi.json` are `None` when `is_production` so prod doesn't leak the endpoint surface.
- Tests: 13 new step-06 tests (settings redaction + fail-fast, cache get_or_set + outage fallback + workspace-key isolation). 85 backend pytest total, 2 frontend, typecheck clean.
- **Live validation passed**: seed produces 5 ready docs, `demo@example.com / demo-pass-1234` logs in. Request-ID `trace-1777516082776` appears verbatim in BOTH api and worker logs (full correlation chain).

---

## Decisions worth remembering

| Decision | Why | Where |
|---|---|---|
| `gemini-2.5-flash` for generation, `gemini-embedding-001` (truncated to 768d via `output_dimensionality`) for embeddings | `gemini-2.5-pro` free tier is 0 RPM; `text-embedding-004` was removed from API access | step 02 + step 03 |
| Hash raw bytes (or canonical JSON) for `content_hash` — not normalized text | Single fast lookup at upload; pre-extraction dedup | `services/api/app/services/dedup.py` |
| `source_score` field on RetrievalCandidate carrying original similarity through fusion | RRF scores (≈ 1/61) are too tiny for confidence thresholds; need real similarity to fall back to when rerank LLM errors | `services/api/app/retrieval/types.py` |
| Streaming endpoint does retrieval BEFORE constructing StreamingResponse; the SSE generator does no DB work | Otherwise SQLAlchemy session lifecycle tangles with the sync Gemini stream + Starlette's disconnect check, raising "close() can't be called here" | `services/api/app/api/ai.py` |
| Ports: web 7000, api 8090 (host), api 8000 (container-internal) | User picked 7000 because 5000 is in Windows TCP exclusion range; 8090 because 8000 is used by another project; container-internal stays 8000 so service-to-service DNS doesn't need host port | step 01 |
| Auth screens stay on a CSS Module, not Tailwind utilities | Conic-gradient halo + pseudo-element neumorphic logo lose fidelity in utility classes | `apps/web/app/(auth)/auth.module.css` |
| HDBSCAN/KMeans skipped in nightly audit | Document-boundary batching adequate for demo corpus; would drag in scikit-learn for marginal benefit | `services/api/app/insights/nightly.py` |
| `frequent_issue` / `emerging_theme` / `missing_context` insight types deferred | Need a query log we don't yet capture, and corpus volume the demo doesn't have | step 05 |

---

## Gotchas caught during validation (don't repeat)

- **chromadb full package needs MSVC on Windows.** Use `chromadb-client` instead — HTTP-only, no native build. Pin to `0.5.23` to match the server image.
- **pydantic-settings JSON-decodes complex env types BEFORE validators run.** Keep `CORS_ORIGINS` as a `str` and parse on read via a property — don't try `list[str]` with a `mode="before"` validator.
- **FastAPI 204 + `-> None` annotation triggers a "must not have a response body" assertion.** Add `response_class=Response, response_model=None` on those routes.
- **Celery `asyncio.run` per task creates a fresh event loop**; the global async engine has connections bound to the previous loop → "Future attached to a different loop". Build a per-task engine inside the task and dispose on exit.
- **Container `node_modules` is a named Docker volume**, so `pnpm install` on the host doesn't reach it. After adding new web deps, `docker compose exec web pnpm install`.
- **Windows host → Docker bind mount file events are flaky.** Adding new App Router pages requires `docker compose restart web` to nudge Next's route scanner.
- **Windows port exclusion ranges block 4940-5039 and 5041-5240.** 7000 is in the safe gap; 5000 is not.
- **`docker compose restart` does NOT reload `.env`.** Use `docker compose up -d --force-recreate <svc>` to pick up new env vars.
- **Shared named volumes inherit the uid/gid of the first container that wrote to them.** When switching api/worker to non-root, recreate the `uploads_data` volume once or chown via a root sidecar.
- **email-validator rejects `.local` TLD (RFC 6762 reserved).** Use `example.com` (RFC 2606) for demo emails.
- **Celery's `setup_logging` signal must be connected** if you want your own log formatter to win — `worker_process_init` runs after Celery's defaults and won't override them.
- **Gemini free-tier model availability is per-key.** List with `GET https://generativelanguage.googleapis.com/v1beta/models?key=$KEY` before assuming a model exists.

---

## Live test credentials (dev only)

```
http://localhost:7000/login
demo@example.com / demo-pass-1234
```

The seed produces 5 docs that include a deliberate conflict (`policies-old.md`
vs `policies-new.md`), so the Insights page populates within ~10 seconds of
the docs reaching `ready`.

---

## Next up

**Step 08 — Final Delivery Checklist** — README polish, demo script, smoke-test runbook, the "would I ship this?" review.

No carryovers from Step 07 — every acceptance criterion is now validated end-to-end.
