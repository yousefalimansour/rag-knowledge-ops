# Step 08 — Final Delivery Checklist

## Objective

Verify, top-to-bottom, that the project is shippable: every brief requirement is met, every "bonus" treated as mandatory is in, the demo flow is rehearsed, the README explains everything, and there are no rough edges a reviewer would trip over.

## User Value

A reviewer evaluating this for a hiring decision can run one command, read one README, and complete the demo flow in under 10 minutes — and walk away with a clear signal on every dimension the brief calls out.

## How to Use This Checklist

Walk it in order. Anything unchecked is a release-blocker. If something is intentionally not done, document **what's missing**, **why it's blocked**, and **what to do next** in this same file under "Known Gaps".

---

## 1. Documentation

- [ ] `README.md` at repo root with:
  - One-paragraph product description.
  - Architecture diagram (ASCII or image).
  - Quickstart: `cp .env.example .env`, `docker compose up`, seed command, demo URL.
  - Feature checklist (mirroring this file).
  - Tech stack and rationale.
  - Test commands.
  - Eval harness explanation + how to run it.
  - Known gaps and tradeoffs.
- [ ] `.env.example` complete with comments for every variable.
- [ ] `.claude/claude.md` up to date and accurate.
- [ ] All `steps/0X-*.md` files reflect what was actually built (deviations recorded).

## 2. Backend Endpoints

- [ ] `POST /auth/signup`
- [ ] `POST /auth/login`
- [ ] `POST /auth/logout`
- [ ] `GET /auth/me`
- [ ] `POST /api/ingest/files`
- [ ] `POST /api/ingest/source`
- [ ] `GET /api/docs`
- [ ] `GET /api/docs/:id`
- [ ] `GET /api/jobs/:id`
- [ ] `GET /api/jobs/stream` (SSE)
- [ ] `POST /api/ai/query`
- [ ] `POST /api/ai/query/stream` (SSE)
- [ ] `GET /api/search`
- [ ] `GET /api/ai/insights`
- [ ] `GET /api/ai/insights/:id`
- [ ] `PATCH /api/ai/insights/:id`
- [ ] `POST /api/insights/run`
- [ ] `GET /api/insights/runs`
- [ ] `GET /api/notifications`
- [ ] `PATCH /api/notifications/:id`
- [ ] `POST /api/notifications/mark-all-read`
- [ ] `GET /api/health`
- [ ] All non-auth endpoints require auth.
- [ ] All endpoints workspace-scoped where applicable.

## 3. Ingestion

- [ ] PDF, TXT, MD, Slack JSON, Notion JSON ingestion all work end-to-end.
- [ ] MIME validation by content sniffing.
- [ ] Upload size enforced.
- [ ] Background processing via Celery; API never blocks on LLM.
- [ ] Job status visible (REST + SSE).
- [ ] Deduplication by content hash.
- [ ] Versioning on changed content with same title.
- [ ] Embedding cache reused on identical chunks.
- [ ] Chroma collection populated with workspace-tagged metadata.

## 4. Retrieval & Reasoning

- [ ] Query rewriting (with heuristic skip).
- [ ] Hybrid search: vector + keyword + RRF fusion.
- [ ] Gemini reranker (with fusion fallback).
- [ ] Filters: source_types, document_ids, date range.
- [ ] Citations always reference retrieved chunk ids.
- [ ] Citation post-validation drops unknown ids.
- [ ] Confidence score computed and returned.
- [ ] Refusal contract: no citations, low confidence, explicit "not enough evidence" answer.
- [ ] Cache hits avoid the LLM call.
- [ ] Streaming endpoint emits start → token+ → sources → confidence → done.

## 5. Proactive Intelligence

- [ ] `generate_insights_scoped` runs post-ingest automatically.
- [ ] Coordinator (`*/30 * * * *`) runs and only processes deltas via watermark.
- [ ] Nightly audit runs (configurable cron) and produces cross-doc insights.
- [ ] Manual trigger endpoint works and persists a `insight_runs` row.
- [ ] All required insight types implemented: conflict, frequent_issue, repeated_decision, emerging_theme, stale_document, missing_context.
- [ ] `dedup_hash` prevents duplicate insights across runs.
- [ ] Each insight links evidence chunks; UI preview opens them.
- [ ] Severity assigned to every insight.
- [ ] Run history (status, errors, scope, watermark, counts) persisted.

## 6. Notifications

- [ ] Persisted in Postgres.
- [ ] Bell UI with unread count.
- [ ] Mark-read on click; mark-all-read endpoint works.
- [ ] Severity badges visible.
- [ ] Click-through to source insight or document.
- [ ] High-severity insight creation triggers a notification.
- [ ] Ingest completed/failed creates a notification for the uploader.
- [ ] Real-time delivery via the shared SSE channel.

## 7. Auth & Security

- [ ] Real signup + login + logout.
- [ ] HTTP-only cookies, CSRF protection on state-changing requests.
- [ ] Argon2id (or bcrypt cost ≥ 12) password hashing.
- [ ] Workspace isolation enforced at every read/write.
- [ ] Rate limiting on auth, ingestion, and AI query endpoints.
- [ ] Secrets only in env, never logged or committed.
- [ ] CORS configured explicitly with credentials.
- [ ] Upload limits + MIME sniffing.
- [ ] Prompt-injection mitigations: delimited context, no user content in instruction slot.

## 8. Frontend Quality

- [ ] First screen after login is the dashboard, not a marketing page.
- [ ] All seven screens implemented and visually consistent.
- [ ] Streaming answers render token-by-token.
- [ ] Source preview panel works and shows chunk in surrounding context.
- [ ] Job status updates live without reload.
- [ ] Notification bell shows real persisted state.
- [ ] Empty / loading / error states everywhere.
- [ ] Responsive at 360px viewport.
- [ ] No console errors on the happy path.
- [ ] Lighthouse a11y ≥ 95 on Copilot and Documents.

## 9. Infrastructure

- [ ] `docker compose up` brings the full stack to healthy in under ~60s.
- [ ] Healthchecks on db, cache, vector, api.
- [ ] Restart policies set; named volumes used; non-root container users.
- [ ] Migrations run on api startup.
- [ ] `make seed` creates a fully usable demo state.
- [ ] Logs are structured JSON with request/correlation IDs.
- [ ] Errors return RFC 7807.
- [ ] Rate limiting configurable via env.
- [ ] `/api/health` deep-checks DB, Redis, Chroma.

## 10. Testing & Evaluation

- [ ] `make test` runs unit + integration + worker + frontend-unit and passes.
- [ ] `make e2e` runs the Playwright happy path and passes.
- [ ] `make eval` runs the ~15 Q&A retrieval-quality harness and passes thresholds.
- [ ] Coverage targets met on critical modules.
- [ ] Linters + type-checkers pass.

## 11. Demo Rehearsal (do this before declaring done)

Run through the full reviewer flow on a clean machine:

1. Clone repo, `cp .env.example .env`, set `GOOGLE_API_KEY`.
2. `docker compose up` → all services healthy.
3. `make seed` → demo workspace populated.
4. Open `http://localhost:3000` → land on login.
5. Log in as the demo user.
6. Upload a fresh PDF from `seed/extra/` → watch status go pending → processing → ready (live, no reload).
7. Open Knowledge Search → query a known phrase → matches highlighted.
8. Open Copilot → ask a question that should produce an answer with citations → watch streaming → click a citation → preview panel shows the chunk.
9. Ask a question outside the corpus → see refusal styling.
10. Trigger `POST /api/insights/run` (or via UI) → notification appears in bell within seconds.
11. Open Insights → see grouped, severity-tagged insights including a conflict with two source links.
12. Click an insight evidence → preview panel opens.
13. Mark a notification read → unread count drops.
14. Stop the API container → `/api/health` reports `db: "ok"`, `api: "down"` from web's perspective; UI shows reconnect state cleanly.
15. Restart → state recovers without page reload.

## 12. Final File-Level Sanity Sweep

- [ ] No commented-out code or `TODO`s without an owner reference.
- [ ] No leftover `print()`/`console.log` debug calls.
- [ ] No `.env`, secrets, or large binaries committed.
- [ ] License file present (MIT or similar) — optional but recommended.
- [ ] Repo size reasonable; `node_modules`, `__pycache__`, build artifacts gitignored.

## 13. Known Gaps & Tradeoffs (fill in as needed)

> Document anything intentionally not done, with three lines: **what**, **why**, **next**.

- _none yet_

---

## Definition of Done (final)

The project is **done** only when every box above is checked, the demo rehearsal completes without surprises, and the README accurately reflects the running system.
