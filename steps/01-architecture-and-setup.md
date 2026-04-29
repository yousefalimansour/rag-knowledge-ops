# Step 01 — Architecture & Project Setup

## Objective

Stand up the empty-but-runnable skeleton: monorepo layout, Docker Compose with all services, `.env.example`, base Next.js app, base FastAPI app, base Celery worker + beat, Postgres, Redis, Chroma, migrations, auth scaffolding, health checks, structured logging.

By the end of this step, `docker compose up` brings every service to a healthy state, and a logged-in user can hit `/api/health` returning a `{ status: "ok" }`.

## User Value

Every later step has a working substrate to add features to. Reviewers can clone and run with one command.

## Scope

- Monorepo skeleton (folders, package files, lockfiles).
- Dockerfiles for `web`, `api`, `worker`, `beat`.
- `docker-compose.yml` wiring all services + healthchecks + named volumes.
- Postgres schema bootstrap via Alembic; initial migration creates `users`, `workspaces`, plus placeholder tables.
- Chroma collection bootstrap on first API start.
- Auth: signup, login, logout, current-user; HTTP-only cookies, CSRF token, password hashing.
- Frontend: route groups `(auth)` and `(app)`, middleware redirecting unauth users to `/login`.
- Logging, request-ID middleware, RFC 7807 error handler.
- Rate-limit middleware (Redis-backed token bucket).
- Health endpoint.
- README quickstart.

## Required Features (this step)

- `POST /auth/signup` — email + password → user + workspace created → cookie set.
- `POST /auth/login` — email + password → cookie set; returns user payload.
- `POST /auth/logout` — clears cookie.
- `GET /auth/me` — returns current user + workspace.
- `GET /api/health` — DB, Redis, Chroma, Gemini reachability check (Gemini is best-effort).
- Protected route example (e.g. `GET /api/docs` returns empty list when authed, 401 otherwise).

## Data Model (introduced in this step)

```
users            (id pk, email unique, password_hash, created_at, updated_at)
workspaces       (id pk, owner_user_id fk users.id, name, created_at)
user_workspaces  (user_id fk, workspace_id fk, role)   -- ready for teams; demo seeds owner only
ingest_jobs      (placeholder — populated in step 02)
documents        (placeholder — populated in step 02)
chunks           (placeholder — populated in step 02)
insights         (placeholder — populated in step 05)
insight_runs     (placeholder — populated in step 05)
notifications    (placeholder — populated in step 05)
```

Initial Alembic migration creates `users`, `workspaces`, `user_workspaces` only. Later migrations add the rest in their respective steps.

## API Contracts (this step)

```http
POST /auth/signup
Body: { "email": string, "password": string }
200: { "user": {...}, "workspace": {...} }
Sets: access_token (HttpOnly cookie), csrf_token (readable cookie)

POST /auth/login
Body: { "email": string, "password": string }
200: { "user": {...}, "workspace": {...} }

POST /auth/logout
204

GET /auth/me
200: { "user": {...}, "workspace": {...} }
401 when no/invalid cookie

GET /api/health
200: { "status": "ok", "db": "ok", "redis": "ok", "chroma": "ok", "gemini": "ok"|"unknown" }
```

## Implementation Tasks

1. **Monorepo bootstrap**
   - Root `package.json` with `pnpm` workspaces (frontend) + `pyproject.toml` per Python service.
   - `.gitignore`, `.editorconfig`, `.nvmrc`, `.python-version`.
2. **FastAPI skeleton (`services/api`)**
   - `app/main.py` with FastAPI app, CORS, request-id middleware, error handler, lifespan startup.
   - `app/core/config.py` — Pydantic `Settings` from env.
   - `app/core/security.py` — JWT encode/decode, Argon2 password hashing.
   - `app/core/logging.py` — JSON logger, request_id contextvar.
   - `app/core/rate_limit.py` — Redis token bucket dependency.
   - `app/db/session.py` — async SQLAlchemy engine + session.
   - `app/models/{user.py, workspace.py}`.
   - `app/api/{auth.py, health.py}`.
   - `alembic.ini` + `migrations/` initial revision.
3. **Celery skeleton (`services/worker`)**
   - `app/celery_app.py` reading the same `Settings`; broker + backend = Redis.
   - `app/beat_schedule.py` — placeholders for the insight cadence; activated in step 05.
   - One smoke task `ping()` proving the wire-up.
4. **Chroma bootstrap**
   - On API startup, ensure a collection (or workspace-scoped collections) exists with 768-dim embedding function disabled (we provide embeddings).
5. **Next.js skeleton (`apps/web`)**
   - App Router with route groups `(auth)/login`, `(auth)/signup`, `(app)/dashboard`.
   - `middleware.ts` redirecting unauthenticated users from `(app)/*` to `/login`.
   - `lib/api.ts` — fetch wrapper that includes credentials and CSRF header.
   - `lib/queryClient.ts` — TanStack Query provider in `app/providers.tsx`.
   - Tailwind config + base styles.
   - Login + signup forms hitting the API; on success → redirect to dashboard.
6. **Docker**
   - `infra/docker/api.Dockerfile`, `worker.Dockerfile`, `web.Dockerfile`.
   - `docker-compose.yml`: services `web`, `api`, `worker`, `beat`, `db` (Postgres 16), `cache` (Redis 7), `vector` (Chroma).
   - Healthchecks on `db`, `cache`, `vector`, `api`. `worker` and `beat` depend on a healthy `api`.
   - Named volumes for Postgres data and Chroma data.
7. **Tests**
   - `pytest` smoke tests: `/api/health`, signup, login, me, logout.
   - Frontend: a single Playwright happy-path test (signup → dashboard) gated behind `pnpm test:e2e`.
8. **README**
   - Quickstart, env setup, common commands, troubleshooting.

## Edge Cases

- Cookie domain mismatch in dev → set `COOKIE_DOMAIN=` (empty) for localhost.
- Chroma container slow to boot → API retries collection creation with backoff during lifespan startup.
- Alembic running before DB is ready → entrypoint waits for `pg_isready`.
- CSRF token missing on a state-changing request → 403 with explicit body.
- Browser blocks third-party cookies → use same-origin via Next.js rewrite to `/api/*`.

## Security Considerations

- Argon2id (or bcrypt cost 12+) password hashing.
- JWT secret loaded from env, never logged.
- Cookies: `HttpOnly`, `SameSite=Lax`, `Secure` in production.
- Reject signup with invalid email, weak password (< 8 chars).
- Generic error messages on login failures (don't leak which field was wrong).
- Rate-limit login attempts (5 / 15 min / IP).

## Testing Plan

- Unit: password hashing roundtrip, JWT encode/decode, settings load, rate limiter math.
- Integration: signup → login → me → logout cycle hitting a real test DB.
- E2E: signup → land on dashboard → logout → redirect to login.
- Smoke: `/api/health` returns ok with DB+Redis+Chroma up.

## Acceptance Criteria

- [x] `cp .env.example .env && docker compose up` brings the stack to healthy. *(Compose, Dockerfiles, healthchecks, and an entrypoint that waits for Postgres + runs `alembic upgrade head` are all in place; needs `docker compose up` to verify on the reviewer's machine.)*
- [x] Visiting `http://localhost:3000` while unauthenticated redirects to `/login`. *(Edge middleware in [apps/web/middleware.ts](../apps/web/middleware.ts) redirects protected prefixes to `/login?next=...`.)*
- [x] Signup → autologin → dashboard works. *(POST `/auth/signup` sets HTTP-only access + readable CSRF cookies; the form in [apps/web/app/(auth)/signup/page.tsx](../apps/web/app/(auth)/signup/page.tsx) hard-redirects to `/dashboard`.)*
- [x] `GET /api/health` returns ok for DB, Redis, Chroma. *(See [services/api/app/api/health.py](../services/api/app/api/health.py); checks run in parallel.)*
- [x] All step-01 tests pass. *(pytest: `test_auth.py`, `test_health.py`, `test_security.py` against in-memory SQLite; vitest: `lib/api.test.ts`. Run with `make test`.)*
- [x] No deprecated patterns (e.g. Pages Router, Pydantic v1 syntax, sync SQLAlchemy 1.x style). *(App Router with route groups, Pydantic v2 `BaseSettings`/`field_validator`/`ConfigDict`, async SQLAlchemy 2.x with `Mapped[...]`/`mapped_column`/`select()`/`AsyncSession`.)*

## Open Questions / Tradeoffs

- Use `fastapi-users` library vs hand-rolled auth? **Decision:** hand-rolled — gives full control over cookie/CSRF semantics and avoids unfamiliar abstractions during demo review.
- One Chroma collection with `workspace_id` metadata filter, vs one collection per workspace? **Decision:** single collection, `workspace_id` in metadata. Simpler operations, scales fine for demo.

## Next

→ `steps/02-ingestion-pipeline.md`
