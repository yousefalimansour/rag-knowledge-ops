# KnowledgeOps AI — Project Context for Claude

> This file is the durable context for any future Claude session working in this repo. Read it first, every time, before touching code.

---

## 1. Project Name & Mission

**KnowledgeOps AI** — an AI Knowledge Operations System that turns scattered team knowledge (PDFs, docs, Slack, Notion) into searchable, grounded, proactively-surfaced intelligence.

**Mission:** make a team's institutional knowledge answerable. Ingest from many sources, embed and structure it, let users ask questions and receive cited answers, and proactively surface conflicts, recurring issues, and stale information.

## 2. Product Goals

1. Ingest knowledge from heterogeneous sources (PDF, TXT, MD, simulated Slack JSON, simulated Notion JSON).
2. Process every source through a robust pipeline: extract → normalize → chunk → embed → store.
3. Provide grounded Q&A through a hybrid retrieval (vector + keyword) + re-ranking + LLM reasoning pipeline that **always cites sources**.
4. Surface insights proactively — not just on demand. Conflicts, stale docs, recurring issues, repeated decisions.
5. Deliver a polished AI Copilot UI that makes the workflow obvious: upload → process → ask → verify → review insights.
6. Be production-shaped: auth, modular services, background jobs, Docker Compose, logging, rate limiting, caching, tests, an evaluation set.

## 3. Technical Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Next.js (web)  │────▶│  FastAPI (api)   │────▶│ PostgreSQL (db)  │
│  App Router     │ SSE │  Auth + REST     │     │  + pgvector tbls │
│  TanStack Query │     │  Validation      │     └──────────────────┘
└─────────────────┘     │  Rate limit      │              ▲
                        └──────────────────┘              │
                              │  enqueue                  │
                              ▼                           │
                        ┌──────────────────┐     ┌────────┴─────────┐
                        │  Redis (broker   │────▶│  Celery worker   │
                        │   + cache)       │     │  ingest / insight│
                        └──────────────────┘     │  jobs            │
                              ▲                  └────────┬─────────┘
                              │                           │
                        ┌──────────────────┐     ┌────────▼─────────┐
                        │  Celery Beat     │     │  Chroma (vectors)│
                        │  scheduler       │     │  768-dim         │
                        └──────────────────┘     └──────────────────┘
                                                          ▲
                                                          │
                                                  ┌───────┴────────┐
                                                  │ Google AI Studio│
                                                  │ gemini-2.5-pro  │
                                                  │ text-embedding- │
                                                  │ 004 (768d)      │
                                                  └────────────────┘
```

**Service boundaries:**

| Service     | Responsibility                                                                  |
|-------------|---------------------------------------------------------------------------------|
| `web`       | Next.js App Router UI, auth flows, SSE consumption, optimistic UI               |
| `api`       | FastAPI REST + SSE, auth, validation, rate limit, enqueue jobs, **never blocks on LLM calls for ingestion** |
| `worker`    | Celery worker — ingestion pipeline, embedding generation, insight generation    |
| `beat`      | Celery Beat — scheduled jobs (30-min insight coordinator, nightly audit)        |
| `db`        | PostgreSQL — documents, chunks, jobs, users, insights, notifications            |
| `vector`    | Chroma — embeddings + chunk metadata for similarity search                      |
| `cache`     | Redis — Celery broker, query cache, rate-limit counters                         |

## 4. Tech Stack & Reasons

| Layer        | Choice                                          | Reason                                                                 |
|--------------|-------------------------------------------------|------------------------------------------------------------------------|
| Frontend     | Next.js 15 App Router, React 19, TS, Tailwind   | Required by brief. App Router for server components + streaming.       |
| Frontend data| TanStack Query v5                               | Required by brief. Built-in caching + suspense + mutation states.       |
| Backend      | FastAPI (Python 3.12)                           | Required by brief. Async, Pydantic validation, OpenAPI free.           |
| ORM          | SQLAlchemy 2.x + Alembic                        | Standard, async-capable, migration story is solid.                     |
| Database     | PostgreSQL 16                                   | Required by brief. Also stores keyword search via `tsvector`.          |
| Vector store | Chroma (server mode)                            | Required by brief. Local-first, simple, persistent.                    |
| Queue        | Redis 7 + Celery 5 + Celery Beat                | Required by brief. Mature, supports scheduled + on-demand jobs.        |
| LLM          | Google AI Studio — `gemini-2.5-pro`             | User decision. Strong reasoning, native streaming.                     |
| Embeddings   | Google `gemini-embedding-001` (3072d native, truncated to 768d via `output_dimensionality`) | Active embedding model on the user's API key; 768-dim Matryoshka truncation keeps Chroma collection compat. |
| Auth         | FastAPI-Users or hand-rolled JWT (HTTP-only cookie) | Real login, protected frontend + backend routes.                       |
| Streaming    | Server-Sent Events (SSE)                        | User decision. Simpler than WS for one-way streaming.                  |
| Testing      | pytest + httpx + Playwright (frontend) + custom retrieval-quality script | Backend, integration, E2E, RAG eval.    |
| Infra        | Docker Compose                                  | Required by brief. One `docker compose up` to run everything.          |

## 5. Folder Structure

```
rag-knowledge-ops/
├── .claude/
│   └── claude.md                     # this file
├── steps/                            # planning files, one per phase
│   ├── 00-project-understanding.md
│   ├── 01-architecture-and-setup.md
│   ├── 02-ingestion-pipeline.md
│   ├── 03-retrieval-and-reasoning-engine.md
│   ├── 04-ai-copilot-frontend.md
│   ├── 05-proactive-intelligence-layer.md
│   ├── 06-system-design-infrastructure.md
│   ├── 07-testing-evaluation-and-quality.md
│   └── 08-final-delivery-checklist.md
├── apps/
│   └── web/                          # Next.js app
│       ├── app/
│       │   ├── (auth)/login, signup
│       │   ├── (app)/dashboard, documents, upload, search, copilot, insights, settings
│       │   └── api/                  # only frontend-internal route handlers if needed
│       ├── components/
│       ├── lib/                      # api client, sse client, auth helpers
│       ├── hooks/
│       └── styles/
├── services/
│   ├── api/                          # FastAPI app
│   │   └── app/
│   │       ├── main.py
│   │       ├── api/                  # routers: auth, ingest, docs, ai, insights, notifications, jobs, health
│   │       ├── core/                 # config, security, logging, rate-limit, deps
│   │       ├── db/                   # engine, session, base
│   │       ├── models/               # SQLAlchemy ORM
│   │       ├── schemas/              # Pydantic
│   │       ├── services/             # business logic
│   │       ├── repositories/         # DB access
│   │       ├── ai/                   # gemini client, prompts, embeddings
│   │       ├── ingestion/            # extractors, chunker, dedup, version
│   │       ├── retrieval/            # hybrid search, rerank, query rewrite
│   │       ├── insights/             # generators, scopes, dedup
│   │       ├── notifications/        # in-app notification service
│   │       └── tests/
│   └── worker/                       # Celery app — shares modules from api via package import
│       └── app/
│           ├── celery_app.py
│           ├── tasks/                # ingest_document, generate_insights_scoped, nightly_audit, etc.
│           └── beat_schedule.py
├── packages/
│   └── shared-types/                 # OpenAPI-generated TS types for frontend
├── infra/
│   ├── docker/
│   │   ├── api.Dockerfile
│   │   ├── worker.Dockerfile
│   │   └── web.Dockerfile
│   └── migrations/                   # Alembic
├── eval/
│   └── retrieval/                    # ~15 Q&A pairs + pytest harness
├── seed/                             # demo PDFs/MD/JSON
├── docker-compose.yml
├── .env.example
├── README.md
└── .gitignore
```

> **Note:** the FastAPI `api` and Celery `worker` share code (models, services, AI clients) via the same `services/api/app` package mounted in both Docker images. Avoid duplication.

## 6. Backend Responsibilities (`services/api`)

- Authentication (signup, login, logout, current-user, password hashing with Argon2 or bcrypt).
- Issue HTTP-only secure cookie JWTs. CSRF protection for cookie-auth endpoints.
- All `/api/*` endpoints except `/auth/*` and `/health` require auth.
- Validate every input via Pydantic. Reject unknown fields.
- Enforce file upload limits (configurable, default 25 MB) and MIME validation.
- Rate limit per-user and per-IP (Redis token bucket).
- Enqueue heavy work to Celery — never block the request loop on LLM calls during ingestion.
- For `/api/ai/query` and `/api/ai/query/stream` — synchronous retrieval + LLM call is acceptable; cache results.
- Centralized error handler returning RFC 7807 problem details (`type`, `title`, `status`, `detail`, `instance`).
- Structured JSON logging with request ID / correlation ID propagated to workers.
- Health endpoint checks DB, Redis, Chroma, Gemini reachability.

## 7. Frontend Responsibilities (`apps/web`)

### 7.1 Visual design language (locked)

- **Theme:** dark glass-morphism. Source aesthetic: Uiverse `Priyanshu02020` login card. Auth screens render that card verbatim (animated conic-gradient halo, inset highlight shadows, neumorphic logo). Every other screen uses the same palette + shadow tokens via Tailwind theme.
- **Palette tokens** (defined in `apps/web/tailwind.config.ts`):
  - `bg-surface-900` `#1a1a1a` — page background
  - `bg-surface-800` `#222222` — card / panel resting
  - `bg-surface-700` `#272727` — elevated card / login-box
  - `bg-surface-600` `#2f2f2f` — hover / focus lift
  - `bg-control` `#373737` — buttons; `bg-control-input` `#3a3a3a` — inputs
  - `text-ink` `#fff` / `text-ink-muted` `rgba(255,255,255,0.7)` / `text-ink-subtle` `rgba(255,255,255,0.5)` / `border-ink-faint` `rgba(255,255,255,0.12)`
  - `accent` `#7c8cff` — used sparingly for active state, focus rings, links
  - `shadow-card`, `shadow-inset`, `shadow-button` — match Uiverse outer/inset combos
- **Auth screens use a CSS Module** (`apps/web/app/(auth)/auth.module.css`) for the verbatim card + animated halo. Don't migrate this to Tailwind utilities — the conic-gradient and pseudo-element logo lose fidelity.
- **No light mode** for this project.
- **No marketing landing page.** Entry post-login is the dashboard.

### 7.2 Behavior

- Auth flows (login, signup, logout, session refresh) with protected route groups.
- Dashboard, Documents list, Upload, Knowledge Search, AI Copilot (chat), Insights, Notifications, Settings.
- TanStack Query for all server state. SWR-style optimistic updates for mutations.
- SSE consumer for `/api/ai/query/stream` — token-by-token answer rendering with sources arriving at the end.
- Notification bell with unread count, dropdown inbox, real read/unread persistence.
- Source preview panel — click a citation, see the chunk in context.
- Empty states, loading skeletons, error boundaries, retry affordances on every async surface.
- Responsive (desktop primary, mobile usable).
- No marketing landing page — the entry point after login is the dashboard.

## 8. Worker Responsibilities (`services/worker`)

- `ingest_document(doc_id)`: extract → normalize → chunk → embed (batched) → upsert to Chroma → mark complete → trigger scoped insight generation.
- `generate_insights_scoped(doc_ids)`: insights scoped to recently-ingested docs (post-ingest hook).
- `coordinator_30m`: scan changed/unprocessed knowledge since last run; enqueue scoped insight jobs.
- `nightly_audit`: full cross-document scan for conflicts, stale docs, repeated decisions, emerging themes.
- `manual_run(scope)`: triggered by `POST /api/insights/run`.
- All tasks idempotent. Retries with exponential backoff. Errors persisted to `insight_runs` / `ingest_jobs` tables.
- Workers must never duplicate insights — deduplication hash on (type, sorted source ids, normalized title).

## 9. AI / Retrieval Pipeline Responsibilities

**Embeddings:** `text-embedding-004`, 768 dim, batched. Cache by content hash to avoid re-embedding identical chunks.

**Retrieval pipeline (`POST /api/ai/query`):**

1. **Query rewrite** — Gemini rewrites the user question into 1–3 focused search queries (only when the original is conversational/ambiguous).
2. **Hybrid search** — for each rewritten query, run vector search (Chroma top-K) AND keyword search (Postgres `tsvector` top-K) in parallel.
3. **Fusion** — Reciprocal Rank Fusion to merge results.
4. **Re-rank** — Gemini-based pairwise/listwise rerank on top-N candidates (or a lightweight cross-encoder if latency demands).
5. **Filter** — drop chunks below score threshold; deduplicate by document.
6. **Reasoning** — pass top chunks + question to Gemini with a strict prompt: cite sources, refuse if evidence is weak, flag conflicts.
7. **Output** — `{ answer, sources[], confidence, reasoning }`. Confidence = function of (top-score, score gap, source agreement, evidence count).

**Streaming:** `POST /api/ai/query/stream` does steps 1–5 first, then SSE-streams the answer tokens, finally emits a `sources` event then `done`.

**Refusal contract:** if hybrid search returns nothing above threshold, the LLM must answer "I don't have evidence about this in the knowledge base." — no hallucination ever.

**Insights pipeline:** scoped runs prompt Gemini on a small slice (e.g. one new doc + N most-similar existing chunks) for cheap deltas. The nightly audit clusters chunks (e.g. by topic via embeddings + KMeans or HDBSCAN) and asks Gemini to detect conflicts/decisions/trends per cluster.

## 10. Database & Vector Database Responsibilities

**PostgreSQL** owns the source-of-truth records:

- `users` — id, email, password_hash, created_at
- `workspaces` — id, owner_user_id, name (single per user for demo, schema ready for teams)
- `documents` — id, workspace_id, title, source_type, original_filename, content_hash, version, status, chunk_count, source_metadata (jsonb), created_at, updated_at, processed_at
- `chunks` — id, document_id, chunk_index, text, token_count, heading, page_number, source_timestamp, embedding_id, content_tsv (tsvector, indexed), created_at
- `ingest_jobs` — id, document_id, status, error, started_at, finished_at
- `insights` — id, workspace_id, type, title, summary, severity, confidence, evidence (jsonb of source refs), dedup_hash (unique), state (active/dismissed/read), created_at
- `insight_runs` — id, scope, trigger (post_ingest|coordinator|nightly|manual), status, error, source_doc_ids (jsonb), insights_generated, started_at, finished_at
- `notifications` — id, user_id, type, title, body, severity, read_at, link_kind, link_id, created_at
- `query_cache` — content_hash → answer/sources/confidence (optional, opportunistic)

Indexes: `chunks(content_tsv) USING GIN`, `documents(content_hash)`, `insights(dedup_hash) UNIQUE`, `notifications(user_id, read_at, created_at)`.

**Chroma** owns embeddings:

- One collection per workspace (or filter by workspace metadata in a single collection — pick one consistently).
- Each item: `id = chunk_id`, `embedding`, metadata `{ document_id, workspace_id, chunk_index, page, heading, source_type }`.

## 11. Environment Variables (see `.env.example`)

```
# api
APP_ENV=development
SECRET_KEY=...
DATABASE_URL=postgresql+asyncpg://kops:kops@db:5432/kops
REDIS_URL=redis://cache:6379/0
CHROMA_URL=http://vector:8000
CORS_ORIGINS=http://localhost:7000

# auth
JWT_SECRET=...
JWT_ALGORITHM=HS256
ACCESS_TOKEN_TTL_MIN=60
REFRESH_TOKEN_TTL_DAYS=14
COOKIE_SECURE=false   # true in production
COOKIE_DOMAIN=

# google ai studio
GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.5-pro
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768

# limits
MAX_UPLOAD_MB=25
RATE_LIMIT_PER_MIN=60
QUERY_RATE_LIMIT_PER_MIN=20

# beat
INSIGHT_COORDINATOR_CRON=*/30 * * * *
INSIGHT_NIGHTLY_AUDIT_CRON=0 3 * * *

# web — for `next dev` on the host. Inside the web container, docker-compose
# hard-overrides this to http://api:8000 so the rewrite uses container DNS.
NEXT_PUBLIC_API_URL=http://localhost:8090
```

## 12. Local Development Commands

```bash
# one-time
cp .env.example .env
docker compose build

# run everything
docker compose up

# urls — host ports are 5000 (web) and 8090 (api). Container-internal stays
# 8000 for the api so service-to-service DNS does not need to know the host port.
# web:    http://localhost:7000
# api:    http://localhost:8090/docs
# chroma: http://localhost:8001
# db:     postgres://kops:kops@localhost:5432/kops

# migrations
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "msg"

# seed demo data
docker compose exec api python -m app.scripts.seed

# logs
docker compose logs -f api worker beat
```

## 13. Testing Commands

```bash
# backend unit + integration
docker compose exec api pytest -q
docker compose exec api pytest -q app/tests/integration

# retrieval evaluation (RAG quality)
docker compose exec api pytest -q eval/retrieval

# frontend
cd apps/web && pnpm test
cd apps/web && pnpm test:e2e   # Playwright

# all
make test
```

## 14. Coding Conventions

- **Python**: `ruff` + `ruff format`. Type hints required. Async by default. Pydantic v2.
- **TypeScript**: `eslint` + `prettier`. Strict mode. No `any` without comment justifying it.
- **Imports**: absolute imports inside each app/service.
- **Naming**: snake_case Python, camelCase TS, PascalCase components and types, UPPER_SNAKE constants.
- **Files**: one router per resource, one service per domain concept.
- **Comments**: only when WHY is non-obvious. Don't restate the code.
- **Tests**: `test_<unit>.py` colocated under `tests/`. Integration tests use a real Postgres+Redis+Chroma test container.

## 15. Security Rules

- Auth required on every endpoint except `POST /auth/login`, `POST /auth/signup`, `GET /api/health`.
- JWTs in HTTP-only `Secure` `SameSite=Lax` cookies. CSRF token (double-submit) for state-changing requests.
- Hash passwords with Argon2id (or bcrypt cost ≥ 12).
- Validate every uploaded file's MIME by sniffing content, not the client's `Content-Type`. Reject anything that isn't pdf/txt/md.
- Enforce per-user upload size + per-minute rate limits.
- Never log raw documents, secrets, or full prompts. Log redacted metadata.
- Workspace isolation: every read/write filters by `workspace_id`. Add a repository-level guard.
- Treat document content as untrusted. When passing to Gemini, never inject a user-controlled string into a system-prompt slot — always put it in a clearly delimited "context" / "user question" slot.

## 16. Error Handling Rules

- All exceptions caught by a global handler → RFC 7807 problem JSON.
- Domain errors are typed (`NotFoundError`, `PermissionDeniedError`, `IngestionError`, `RetrievalError`, `LLMError`, `RateLimitedError`).
- 4xx for client mistakes, 5xx only for true server faults.
- Workers persist failures to job tables and re-raise to let Celery retry.
- Frontend shows a recoverable error UI on every fetch failure — no silent failures.

## 17. Logging & Observability

- Structured JSON logs to stdout. Fields: `ts`, `level`, `service`, `request_id`, `user_id`, `event`, `latency_ms`, plus event-specific.
- Generate request IDs at API edge; pass to Celery via task headers; log them in worker too.
- Log every ingestion stage: `extract.start`, `extract.done`, `chunk.done`, `embed.done`, `index.done`.
- Log every retrieval: `query.received`, `rewrite.done`, `search.done`, `rerank.done`, `llm.done`, with latencies.
- Expose Prometheus-style `/metrics` if time permits (bonus, not required).

## 18. Definition of Done

The project is done **only when every item below is true**:

- [ ] All required endpoints respond correctly with auth.
- [ ] PDF, TXT, MD, simulated Slack JSON, simulated Notion JSON ingestion all work end-to-end.
- [ ] Background ingestion via Celery — API never blocks on LLM calls during ingestion.
- [ ] Deduplication by content hash works (re-uploading same file does not duplicate).
- [ ] Document versioning works (re-uploading a changed file creates a new version).
- [ ] Embeddings stored in Chroma and searchable.
- [ ] Hybrid search (vector + keyword) with RRF fusion works.
- [ ] Query rewriting and reranking are wired into the pipeline.
- [ ] AI answers always cite sources; refuses on weak evidence.
- [ ] Confidence score returned and visible in UI.
- [ ] Ambiguity / unknown handled with refusal or clarifying response.
- [ ] Frontend supports upload, browse, search, ask (with streaming SSE), inspect sources, view insights.
- [ ] Auth implemented with login, signup, logout, protected routes.
- [ ] Hybrid proactive insights: post-ingest scoped + 30-min coordinator + nightly audit + manual trigger.
- [ ] Insight runs persisted with status, errors, scope, dedup hash, source citations.
- [ ] Real in-app notifications: bell UI, persisted, read/unread, severity, links to insights/docs.
- [ ] Docker Compose runs the full stack.
- [ ] Logging, error handling, caching, rate limiting in place.
- [ ] Tests: unit (chunking, retrieval, services), integration (API), worker job tests, frontend flow tests.
- [ ] Retrieval evaluation script passes ~15 Q&A pairs above target metrics.
- [ ] README explains run + test instructions.
- [ ] `.claude/claude.md` and `steps/` complete and current.

## 19. Mandatory Features (every "bonus" is required)

- Background ingestion jobs ✓
- Deduplication ✓
- Document versioning ✓
- Multi-step retrieval / query rewriting / reranking ✓
- Hybrid search (keyword + vector) ✓
- Streaming responses (SSE) ✓
- Source preview panel ✓
- Search + filters ✓
- Scheduled jobs (post-ingest + 30-min + nightly + manual) ✓
- Insight categorization + severity + dedup ✓
- Real in-app notifications (not mock) ✓
- Separate api / worker / web services ✓
- Caching layer (Redis) ✓
- Rate limiting ✓
- Auth with protected routes ✓
- Retrieval evaluation set + pytest harness ✓

## 20. Working Style for Future Sessions

For each step:

1. Read the matching `steps/0X-*.md` file before coding.
2. Implement minimally to satisfy that step's acceptance criteria.
3. Add tests for the new behavior.
4. Run `make test` (or the relevant subset).
5. Update the step file with any deviations or open issues.
6. Commit with a message referencing the step (`step-02: chunker handles markdown headings`).

If something is blocked, document in the step file: **what's missing**, **why it's blocked**, **what to do next**.
