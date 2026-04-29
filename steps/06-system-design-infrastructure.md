# Step 06 — System Design & Infrastructure

## Objective

Treat this like a real product, not a script. Lock in the modular architecture, the Docker Compose orchestration, environment management, structured logging, request/correlation IDs, rate limiting, caching, validation, error handling, secret hygiene, health checks, migrations, and seed data — so the project survives review by senior engineers.

## User Value

A reviewer cloning the repo runs one command and gets a fully-wired, observable, secured stack. An on-call engineer gets logs they can actually grep, errors they can route, and runbooks they can follow.

## Scope

- Final `docker-compose.yml` with healthchecks, restart policies, named volumes, sensible resource hints.
- Service Dockerfiles (web, api, worker, beat) — multi-stage, slim images.
- `.env.example` complete with comments for every variable.
- Centralized config (Pydantic `Settings`) with environment loading, validation, and "fail fast" on missing required vars.
- Structured JSON logging across all services; request/correlation ID propagated from API → Celery via task headers.
- RFC 7807 problem-details error handler with typed domain errors.
- Rate limiting (Redis token bucket) — different limits per endpoint class.
- Caching layer (Redis) — query cache + retrieval cache + simple key/value helpers.
- File upload limits + MIME sniffing.
- CORS configured for dev (`http://localhost:3000`) and parameterized for prod.
- `/api/health` deep check (DB, Redis, Chroma, Gemini reachability flag).
- Alembic migrations; safe up/down for every migration touched in earlier steps.
- Seed/demo data script (creates a demo user + workspace and ingests 5 demo docs).
- A Makefile or `justfile` with the common commands.

## Required Engineering Quality

| Concern             | Implementation                                                        |
|---------------------|-----------------------------------------------------------------------|
| Modular architecture| `apps/web`, `services/api`, `services/worker`, `packages/shared-types`; each domain in `app/<domain>/` |
| Typed API contracts | Pydantic v2 schemas, OpenAPI auto-export, TS types generated for web   |
| Validation          | Pydantic at every API boundary; reject unknown fields                  |
| Error handling      | Single global handler → RFC 7807; typed domain errors mapped to status |
| Logging             | JSON to stdout, fields: ts, level, service, request_id, user_id, event |
| Correlation IDs     | Generated in API middleware; passed to Celery via `task.headers`       |
| Rate limiting       | Redis token bucket; default 60/min/user, 20/min/user on `/api/ai/query` |
| Caching             | Redis: query cache (10 min TTL), embedding cache (per content hash, no expiry), retrieval cache (per workspace + filters, 5 min TTL) |
| Secret handling     | Loaded from env, never logged, `Settings` redacts known secret fields  |
| Upload limits       | Reject before reading into memory; stream to disk; cap total request   |
| MIME validation     | Sniff content via `python-magic`/`filetype`; do not trust client header|
| CORS                | `CORS_ORIGINS` parsed from env (comma-separated); credentials enabled  |
| Health checks       | `/api/health` returns per-component status; Compose uses it for dependency ordering |
| API docs            | FastAPI's `/docs` exposed only in dev mode                             |
| Migrations          | Alembic; `alembic upgrade head` runs on API container startup          |
| Seed data           | `python -m app.scripts.seed` creates demo user + 5 ingested docs       |

## Compose Topology

```yaml
services:
  db:        postgres:16          (healthcheck: pg_isready)
  cache:     redis:7-alpine       (healthcheck: redis-cli ping)
  vector:    chromadb/chroma      (healthcheck: GET /api/v1/heartbeat)
  api:       build api.Dockerfile (depends_on: db, cache, vector — all healthy)
  worker:    build worker.Dockerfile (depends_on: api healthy, cache healthy)
  beat:      build worker.Dockerfile, command: celery beat (depends_on: cache healthy)
  web:       build web.Dockerfile (depends_on: api healthy)
```

Volumes: `pgdata`, `chroma_data`, `redis_data`. Networks: a single bridge network. Restart policy: `unless-stopped` on all services.

## Implementation Tasks

1. **Finalize Dockerfiles** as multi-stage builds; web image runs `next start` on port 3000; api image runs `uvicorn` with `--proxy-headers` and `--forwarded-allow-ips`.
2. **Compose hardening**: healthchecks, restart, named volumes, depends_on with `condition: service_healthy`.
3. **Settings module** (`app/core/config.py`):
   - `BaseSettings` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.
   - Required fields (`SECRET_KEY`, `JWT_SECRET`, `GOOGLE_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `CHROMA_URL`) — boot fails on missing.
   - `repr` redacts secrets.
4. **Logging module** (`app/core/logging.py`):
   - `structlog`-based or stdlib `logging` with a JSON formatter; `request_id` and `user_id` from contextvars.
   - One configuration entrypoint shared by api + worker.
5. **Request-ID middleware**:
   - Read incoming `X-Request-ID` or generate UUID; set contextvar; echo header on response.
   - On Celery task enqueue, copy current `request_id` into `task.headers`; worker logging picks it up.
6. **Error handler** (`app/core/errors.py`):
   - Define `AppError` base + `NotFoundError`, `PermissionDeniedError`, `ValidationFailed`, `IngestionError`, `RetrievalError`, `LLMError`, `RateLimitedError`, `ConflictError`.
   - Map each to status + RFC 7807 body; include `request_id` in `instance` field.
   - Global FastAPI exception handler.
7. **Rate limiter** (`app/core/rate_limit.py`):
   - Redis Lua-script token bucket; dependency factory `RateLimit(name, per_min)`.
   - Different limits per endpoint class.
   - 429 response carries `Retry-After`.
8. **Cache helpers** (`app/core/cache.py`):
   - Generic `get_or_set(key, ttl, loader)`.
   - Specific helpers for query cache and retrieval cache (with workspace + content-hash keys).
9. **CORS config** parameterized via env.
10. **Health endpoint** deep-checks DB (`SELECT 1`), Redis (`PING`), Chroma heartbeat. Gemini check is optional and best-effort (don't fail health on Gemini outage; surface it as `gemini: "unknown"` or `"ok"`).
11. **Alembic**:
   - `migrations/env.py` reads URL from settings.
   - Each prior step's tables included in revisions.
   - API container entrypoint runs `alembic upgrade head` before `uvicorn`.
12. **Seed script** (`app/scripts/seed.py`):
   - Creates demo user (email/password from env, defaults documented).
   - Creates a workspace.
   - Ingests 5 fixtures from `seed/` (PDF + 2 MD + Slack JSON + Notion JSON).
   - Triggers an immediate insight run for instant demo content.
13. **Makefile / justfile** with: `up`, `down`, `logs`, `migrate`, `seed`, `test`, `eval`, `fmt`, `lint`.

## Edge Cases

- API booting before Postgres is reachable → entrypoint waits with `pg_isready`-style loop, max 30s.
- Chroma collection dimension mismatch → fail fast at startup with explicit error referencing `EMBEDDING_DIM`.
- Mismatched `JWT_SECRET` between api and worker (if worker ever needs it) → standardize on api owning auth; worker doesn't authenticate, just inherits trust from being on the same internal network.
- Filesystem permissions on Docker volumes (Windows / WSL) → document in README; volumes use named volumes, not bind mounts, by default.
- `.env` accidentally committed → `.gitignore` blocks `.env`; only `.env.example` is tracked.
- Worker process crash loops → Compose restart policy + alerting via log lines (no real alerting in demo, but format is grep-friendly).

## Security Considerations

- All secrets via env; `.env` ignored; `.env.example` carries placeholder values only.
- Production-mode flags: `COOKIE_SECURE=true`, `APP_ENV=production`, FastAPI `/docs` disabled.
- Rate limit on auth endpoints stricter than the default.
- CORS origins explicit — never `*` when credentials are enabled.
- Sanitize logs: no raw bodies, no Authorization header, no document content; truncate long fields.
- Container users: non-root in api, worker, web images.

## Testing Plan

- **Smoke**: `docker compose up` from a clean state → all healthchecks green within 60s.
- **Migration**: `alembic downgrade -1 && alembic upgrade head` round-trips clean.
- **Logging**: a request with `X-Request-ID: abc` produces logs with `request_id=abc` in api, worker (when ingestion is triggered), and beat.
- **Rate limit**: hammering `/api/ai/query` past the limit yields 429 with `Retry-After`.
- **Cache**: repeated identical query hits the cache (verifiable via log absence of `llm.done` or via metric).
- **Health**: stop Postgres → `/api/health` reports `db: "down"` and 503; bring it back → recovers.
- **Seed**: `make seed` from a clean DB → demo user can log in and sees 5 docs ready.

## Acceptance Criteria

- [ ] One command (`docker compose up`) runs the whole stack to healthy.
- [ ] `.env.example` documents every required and optional variable.
- [ ] Logs are JSON, structured, with request/correlation IDs propagating to workers.
- [ ] Errors return RFC 7807 problem details consistently.
- [ ] Rate limiting and caching are observable and tunable via env.
- [ ] Migrations run automatically on api startup; a fresh DB ends up at the latest schema.
- [ ] `make seed` produces a fully usable demo state.
- [ ] No secrets in logs, repo, or images.

## Next

→ `steps/07-testing-evaluation-and-quality.md`
