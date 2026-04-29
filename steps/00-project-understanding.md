# Step 00 — Project Understanding

## Objective

Establish a shared, written understanding of the product, its users, the success criteria, and the non-negotiable constraints — so every later step can be evaluated against the same target.

## User Value

A founding-style engineer reviewing this repo (or a future Claude session) can read this single file and know **what we're building, for whom, why, and what "good" looks like** without re-reading the entire brief.

## Scope

This step is documentation-only. No code is written. The deliverable is alignment, recorded.

## Product One-Liner

KnowledgeOps AI is an AI Knowledge Operations System: it ingests team knowledge from files and simulated team chat/wiki sources, stores it as searchable intelligence, answers questions with cited sources, and proactively surfaces conflicts, recurring issues, stale documents, and emerging themes.

## Primary Users

1. **Knowledge worker** — uploads docs, asks questions, expects answers grounded in their team's content.
2. **Team lead / ops** — wants to see proactive insights (conflicts between policies, support pain points, decisions repeated across teams).
3. **Reviewer / hiring engineer** — evaluates this as a portfolio/hiring artifact: must demonstrate fullstack engineering, system design, AI integration, and product polish.

## Success Criteria (what "shipped" means)

A reviewer can:

1. `docker compose up` and have the full stack running locally with no extra steps.
2. Sign up, log in, land on a dashboard.
3. Upload a PDF, watch its processing status update in near-real-time.
4. Push simulated Slack/Notion JSON via a documented endpoint or seed script.
5. Ask a natural-language question in the Copilot, see the answer stream in via SSE, see citations, click a citation, see the source chunk in context.
6. Open the Insights screen and see grouped, severity-tagged insights generated automatically — including at least one conflict and one stale-doc example from the seeded data.
7. See an in-app notification when a new insight is created.
8. Run `make test` and have all tests (unit, integration, retrieval-eval) pass.

## Non-Functional Requirements

- **Correctness over confidence.** No hallucinations. Refusal beats fabrication.
- **Background work for heavy paths.** API never blocks on LLM calls during ingestion.
- **Auth on every protected endpoint.** Workspace-scoped data access.
- **Observability.** Structured logs with correlation IDs. Job and run history persisted.
- **Reproducibility.** Single `.env.example`, single `docker compose up`, seeded demo data.

## Hard Decisions (locked in this session, do not re-litigate without explicit user input)

| Decision                  | Choice                                                                |
|---------------------------|-----------------------------------------------------------------------|
| LLM                       | Google AI Studio — `gemini-2.5-pro`                                   |
| Embeddings                | `text-embedding-004`, 768 dim                                         |
| Streaming                 | Server-Sent Events (SSE)                                              |
| Backend                   | FastAPI                                                               |
| Frontend                  | Next.js App Router + TS + Tailwind + TanStack Query                   |
| RDBMS                     | PostgreSQL                                                            |
| Vector store              | Chroma                                                                |
| Queue                     | Redis + Celery + Celery Beat                                          |
| Auth                      | JWT in HTTP-only cookies, real signup/login, protected routes         |
| Workspace model           | Single workspace per user for the demo, schema ready for multi-user   |
| Insight cadence           | Hybrid: post-ingest scoped + every-30m coordinator + nightly audit + manual |
| Notifications             | Real in-app system (Postgres-backed, bell UI, read/unread, severity)  |
| Eval set                  | ~15 Q&A pairs with expected source docs, pytest-driven                |
| Repo layout               | Monorepo: `apps/web`, `services/api`, `services/worker` share code    |

## Mandatory Features (treat every original "bonus" as required)

- Background ingestion jobs
- Deduplication by content hash
- Document versioning
- Multi-step retrieval (query rewriting, reranking)
- Hybrid search (vector + keyword)
- Streaming responses (SSE)
- Source preview panel
- Search + filters
- Scheduled insight jobs (multiple cadences as above)
- Insight categorization, severity, dedup, citations
- Real in-app notifications
- Separate api / worker / web services
- Redis caching layer
- Rate limiting
- Auth with protected routes everywhere
- Retrieval-quality evaluation harness

## Out of Scope (for the demo)

- Real Slack / Notion OAuth integration (we use simulated JSON).
- Real email or push notification delivery (in-app only).
- Multi-tenant team management UI (schema is ready; UI is single-workspace).
- Production deployment (Compose-only).
- Mobile-native apps.

## Risks & Mitigations

| Risk                                              | Mitigation                                                            |
|---------------------------------------------------|-----------------------------------------------------------------------|
| Gemini latency on rerank inflates query time      | Use small candidate set (top-20 → rerank top-8), cache by question hash |
| Embedding cost on large uploads                   | Batch embed, dedupe by chunk hash, soft cap on file size (25 MB)      |
| Chroma collection drift if dim mismatch           | Hard-code 768 dim in collection creation; assert at boot              |
| Worker silently drops jobs                        | Persist `ingest_jobs` and `insight_runs` tables; surface in UI        |
| Hallucinated citations                            | Strict prompt: cite chunk_id; post-validate that every cited id was retrieved |
| Insight spam from re-runs                         | `dedup_hash` unique index on (type, sorted source ids, normalized title) |

## Acceptance Criteria for Step 00

- [x] `.claude/claude.md` exists with full architecture.
- [x] All nine `steps/*.md` files exist before any implementation.
- [ ] Reviewer can read this file and answer: what is it, who's it for, what's locked, what's out of scope, how do we know it's done.

## Next

→ `steps/01-architecture-and-setup.md`
