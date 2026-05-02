<div align="center">

# 🧠 KnowledgeOps AI

### *Turn scattered team knowledge into searchable, grounded, proactively-surfaced intelligence.*

[![Status](https://img.shields.io/badge/status-in_development-orange?style=flat-square)](./steps)
[![License](https://img.shields.io/badge/license-Apache_2.0-blue?style=flat-square)](./LICENSE)
[![Stack](https://img.shields.io/badge/stack-Next.js%20·%20FastAPI%20·%20Postgres%20·%20Chroma%20·%20Celery-blueviolet?style=flat-square)](#-tech-stack)
[![AI](https://img.shields.io/badge/AI-Gemini%202.5%20Pro-4285F4?style=flat-square&logo=google)](https://ai.google.dev/)
[![Docker](https://img.shields.io/badge/run-docker%20compose%20up-2496ED?style=flat-square&logo=docker)](#-quick-start)

</div>

---

## 💡 What it does

Modern teams are drowning in information — docs in Notion, conversations in Slack, decisions lost in meetings, repeated questions in support logs. **KnowledgeOps AI** ingests knowledge from many sources, structures it into a queryable knowledge base, and gives your team:

- **Grounded answers** — every claim cites the chunk it came from. No hallucinations. Refusal beats fabrication.
- **Hybrid retrieval** — vector + keyword + RRF fusion + LLM reranking, with query rewriting for conversational input.
- **Streaming Copilot UI** — token-by-token answers via SSE, source preview panel, confidence indicators.
- **Proactive insights** — the system scans your knowledge base on multiple cadences and surfaces conflicts, recurring issues, repeated decisions, stale documents, and emerging themes.
- **Real in-app notifications** — bell, unread state, severity, click-through to evidence.

> Built as a submission for the **Code Quests** hiring quest *Core Software Engineer (Founding Engineer)* at a FinTech serving Egypt's e-commerce ecosystem. Quest [#79](https://app.code-quests.com/quest-view/79).

---

## 🏗️ Architecture

```mermaid
flowchart LR
    User((👤 User))
    subgraph Frontend
        Web["🌐 <b>Next.js Web</b><br/>App Router · TS<br/>TanStack Query · SSE"]
    end
    subgraph Backend
        API["⚡ <b>FastAPI</b><br/>Auth · REST · SSE<br/>Validation · Rate limit"]
        Worker["🛠️ <b>Celery Worker</b><br/>Ingest · Embed<br/>Insight gen"]
        Beat["⏰ <b>Celery Beat</b><br/>Coordinator 30m<br/>Nightly audit"]
    end
    subgraph Stores
        DB[("🐘 <b>Postgres</b><br/>docs · chunks · jobs<br/>insights · notifs")]
        Vec[("🔍 <b>Chroma</b><br/>768d embeddings")]
        Cache[("⚡ <b>Redis</b><br/>broker · cache<br/>rate-limit")]
    end
    subgraph External
        Gemini["🤖 <b>Gemini 2.5 Pro</b><br/>+ text-embedding-004"]
    end

    User --> Web
    Web -->|cookie auth + SSE| API
    API --> DB
    API --> Vec
    API --> Cache
    API -->|enqueue| Cache
    Cache -->|consume| Worker
    Beat -->|schedule| Cache
    Worker --> DB
    Worker --> Vec
    Worker --> Gemini
    API --> Gemini

    classDef svc fill:#1e293b,stroke:#3b82f6,color:#fff
    classDef store fill:#312e81,stroke:#a78bfa,color:#fff
    classDef ext fill:#7c2d12,stroke:#fb923c,color:#fff
    class Web,API,Worker,Beat svc
    class DB,Vec,Cache store
    class Gemini ext
```

**Service boundaries** — each runs in its own Docker container, scales independently, and is healthchecked by Compose.

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 📥 Multi-Source Ingestion
- PDF, TXT, MD file upload
- Simulated Slack & Notion JSON
- MIME sniffing (no header trust)
- Background processing (Celery)
- **Deduplication** by content hash
- **Versioning** on changed content
- Job-status tracking (REST + SSE)
- Embedding cache by chunk hash

### 🔍 Hybrid Retrieval
- Vector search (Chroma)
- Keyword search (Postgres `tsvector`)
- **Reciprocal Rank Fusion**
- Gemini-based listwise rerank
- Query rewriting (with heuristic skip)
- Filters: source / doc / date range
- Citation post-validation
- Calibrated confidence score
- Strict refusal on weak evidence

</td>
<td width="50%" valign="top">

### 🤖 AI Copilot
- Streaming answers via **SSE**
- Inline citation chips
- **Source preview panel**
- Confidence + reasoning summary
- Refusal-aware UI
- Knowledge Search (no-LLM debug)
- Live document status updates

### 🔔 Proactive Intelligence
- **Post-ingest** scoped runs
- **30-min** delta coordinator
- **Nightly** cross-doc audit
- Manual trigger endpoint
- 6 insight types (conflict, frequent_issue, repeated_decision, emerging_theme, stale_document, missing_context)
- Persisted run history + dedup hash
- **Real in-app notifications** (bell, unread, severity)

### 🔐 Production-Shaped
- Auth: signup/login/logout, JWT cookies, CSRF
- Workspace-scoped data
- Per-endpoint rate limits
- RFC 7807 errors · structured logs · request IDs
- Migrations · seed data · health deep-checks

</td>
</tr>
</table>

---

## 🧰 Tech Stack

| Layer            | Choice                                          | Why                                                |
|------------------|-------------------------------------------------|---------------------------------------------------|
| **Frontend**     | Next.js 15 App Router, React 19, TS, Tailwind   | Server components + streaming, native SSE         |
| **Frontend data**| TanStack Query v5                               | Cache + suspense + mutation states                |
| **Backend**      | FastAPI · Python 3.12 · SQLAlchemy 2 · Alembic  | Async, Pydantic, free OpenAPI                     |
| **Database**     | PostgreSQL 16                                   | + `tsvector` GIN index for keyword search         |
| **Vector store** | Chroma                                          | Local-first, persistent, simple ops               |
| **Queue**        | Redis 7 + Celery 5 + Celery Beat                | Mature; on-demand + scheduled jobs                |
| **LLM**          | Google AI Studio — `gemini-3.1-flash-lite-preview` | Higher RPD on free tier; switched from 2.5 Pro / 2.5 Flash to clear rate limits |
| **Embeddings**   | `gemini-embedding-001` truncated to 768d via `output_dimensionality` | Matryoshka truncation keeps the Chroma collection dim consistent |
| **Streaming**    | Server-Sent Events                              | Simpler than WS for one-way streams               |
| **Tests**        | pytest · httpx · Playwright · custom RAG eval   | Unit · integration · worker · E2E · quality       |
| **Infra**        | Docker Compose                                  | One command to run the whole stack                |

---

## 🚀 Quick Start

```bash
# 1. clone & configure
git clone https://github.com/yousefalimansour/rag-knowledge-ops.git
cd rag-knowledge-ops
cp .env.example .env
# edit .env — at minimum set GOOGLE_API_KEY

# 2. run everything
docker compose up

# 3. seed the demo workspace
docker compose exec api python -m app.scripts.seed

# 4. open the app
open http://localhost:7000
```

| Service            | URL / Port                    |
|--------------------|-------------------------------|
| 🌐 Web             | http://localhost:7000         |
| ⚡ API + OpenAPI   | http://localhost:8090/docs    |
| 🔍 Chroma          | http://localhost:8001         |
| 🐘 Postgres        | `postgres://kops:kops@localhost:5432/kops` |
| ⚡ Redis           | `redis://localhost:6379`      |

---

## 📊 Pipelines

### Ingestion — async by design

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant W as 🌐 Web
    participant A as ⚡ API
    participant Q as ⚡ Redis
    participant K as 🛠️ Worker
    participant G as 🤖 Gemini
    participant D as 🐘 DB
    participant V as 🔍 Chroma

    U->>W: drop PDF
    W->>A: POST /api/ingest/files
    A->>A: validate MIME + size
    A->>D: create document (status=pending)
    A->>D: create ingest_job
    A->>Q: enqueue ingest_document(id)
    A-->>W: 202 { job_id }
    W->>A: open SSE /api/jobs/stream
    Q->>K: dispatch task
    K->>K: extract → normalize → chunk
    K->>D: update job stage=embed
    K->>G: embed batches (cached by hash)
    G-->>K: 768d vectors
    K->>D: write chunks (with tsvector)
    K->>V: upsert vectors + metadata
    K->>D: status=ready, processed_at
    K->>Q: enqueue generate_insights_scoped
    A-->>W: SSE event { status=ready }
```

### RAG Query — hybrid + rerank + cite

```mermaid
flowchart TD
    Q[/"❓ User question"/]
    QR{rewrite<br/>needed?}
    QR2["🔁 Query rewriter<br/>(Gemini)"]
    Vec["🔍 Vector search<br/>Chroma · top-K"]
    KW["🔤 Keyword search<br/>Postgres tsvector · top-K"]
    F["⚖️ Reciprocal Rank Fusion<br/>k=60"]
    R["🎯 Listwise rerank<br/>(Gemini · top-20→8)"]
    TH{"score<br/>≥ threshold?"}
    Refuse["🛑 Refusal<br/>'no evidence in KB'<br/>confidence ≤ 0.2"]
    LLM["🧠 Reasoning<br/>(Gemini)<br/>strict cite-only prompt"]
    Val["✅ Citation post-validate<br/>drop unknown chunk_ids"]
    Conf["📈 Confidence<br/>top score · gap · agreement"]
    Out[/"💬 answer + sources[]<br/>+ confidence + reasoning"/]

    Q --> QR
    QR -- yes --> QR2 --> Vec & KW
    QR -- no --> Vec & KW
    Vec --> F
    KW --> F
    F --> R --> TH
    TH -- no --> Refuse --> Out
    TH -- yes --> LLM --> Val --> Conf --> Out

    classDef start fill:#0ea5e9,stroke:#0369a1,color:#fff
    classDef proc fill:#1e293b,stroke:#3b82f6,color:#fff
    classDef refuse fill:#7f1d1d,stroke:#ef4444,color:#fff
    classDef out fill:#166534,stroke:#22c55e,color:#fff
    class Q start
    class QR2,Vec,KW,F,R,LLM,Val,Conf proc
    class Refuse refuse
    class Out out
```

### Proactive Insights — four cadences, one engine

```mermaid
stateDiagram-v2
    direction LR
    [*] --> PostIngest: doc becomes ready
    [*] --> Coordinator: every 30 min
    [*] --> Nightly: 03:00 daily
    [*] --> Manual: POST /api/insights/run

    PostIngest --> Scoped: doc_ids slice
    Coordinator --> Scoped: changed since watermark
    Nightly --> FullAudit: cluster + cross-doc
    Manual --> Scoped: scope=docs|type|all

    Scoped --> Generators
    FullAudit --> Generators
    Generators --> Dedup
    Dedup --> Persist: insert if new<br/>(unique dedup_hash)
    Dedup --> Skip: collision → counter++
    Persist --> Notify: severity ≥ medium
    Notify --> [*]
    Skip --> [*]
```

### Auth — cookie + CSRF

```mermaid
sequenceDiagram
    autonumber
    participant W as 🌐 Web
    participant A as ⚡ API
    participant D as 🐘 DB
    W->>A: POST /auth/login {email, pw}
    A->>D: fetch user
    D-->>A: row
    A->>A: argon2.verify(pw, hash)
    A->>A: sign JWT (sub=user_id, ws=workspace_id)
    A-->>W: Set-Cookie: access_token (HttpOnly Secure SameSite=Lax)
    A-->>W: Set-Cookie: csrf_token (readable, double-submit)
    W->>A: POST /api/* (cookie + X-CSRF-Token header)
    A->>A: verify cookie + CSRF + workspace scope
    A-->>W: 200 / 401 / 403
```

---

## 🗄️ Data Model

```mermaid
erDiagram
    USERS ||--o{ USER_WORKSPACES : member_of
    WORKSPACES ||--o{ USER_WORKSPACES : has
    WORKSPACES ||--o{ DOCUMENTS : owns
    WORKSPACES ||--o{ INSIGHTS : owns
    WORKSPACES ||--o{ INSIGHT_RUNS : owns
    DOCUMENTS ||--o{ CHUNKS : has
    DOCUMENTS ||--o{ INGEST_JOBS : tracked_by
    USERS ||--o{ NOTIFICATIONS : receives
    INSIGHTS }o--|| NOTIFICATIONS : may_link

    USERS {
        uuid id PK
        text email UK
        text password_hash
        timestamptz created_at
    }
    WORKSPACES {
        uuid id PK
        uuid owner_user_id FK
        text name
    }
    DOCUMENTS {
        uuid id PK
        uuid workspace_id FK
        text title
        text source_type
        text content_hash
        int version
        text status
        jsonb source_metadata
        int chunk_count
    }
    CHUNKS {
        uuid id PK
        uuid document_id FK
        int chunk_index
        text text
        text text_hash
        int token_count
        text heading
        int page_number
        tsvector content_tsv
    }
    INGEST_JOBS {
        uuid id PK
        uuid document_id FK
        text status
        text stage
        text error
        int attempts
    }
    INSIGHTS {
        uuid id PK
        uuid workspace_id FK
        text type
        text title
        text severity
        float confidence
        jsonb evidence
        text dedup_hash UK
        text state
    }
    INSIGHT_RUNS {
        uuid id PK
        uuid workspace_id FK
        text scope
        text trigger
        text status
        timestamptz watermark_after
        int insights_generated
    }
    NOTIFICATIONS {
        uuid id PK
        uuid user_id FK
        text type
        text severity
        text link_kind
        uuid link_id
        timestamptz read_at
    }
```

---

## 📡 API

| Method | Endpoint                          | Purpose                                   |
|--------|-----------------------------------|-------------------------------------------|
| POST   | `/auth/signup`                    | Create user + workspace, set cookie       |
| POST   | `/auth/login`                     | Authenticate, set cookie                  |
| POST   | `/auth/logout`                    | Clear cookie                              |
| GET    | `/auth/me`                        | Current user + workspace                  |
| POST   | `/api/ingest/files`               | Upload PDF / TXT / MD (multipart)         |
| POST   | `/api/ingest/source`              | Ingest simulated Slack / Notion JSON      |
| GET    | `/api/docs`                       | List documents (filters + pagination)     |
| GET    | `/api/docs/:id`                   | Document detail + chunk preview           |
| GET    | `/api/jobs/:id`                   | Ingestion job status                      |
| GET    | `/api/jobs/stream`                | **SSE** — live job + notification stream  |
| GET    | `/api/search`                     | Hybrid search results (no LLM)            |
| POST   | `/api/ai/query`                   | RAG answer (sync, JSON)                   |
| POST   | `/api/ai/query/stream`            | **SSE** — streamed answer + sources       |
| GET    | `/api/insights`                   | List insights (filters)                   |
| GET    | `/api/insights/:id`               | Insight detail + linked docs              |
| PATCH  | `/api/insights/:id`               | Mark read / dismissed                     |
| POST   | `/api/insights/run`               | Trigger manual insight generation         |
| GET    | `/api/insights/runs`              | Run history                               |
| GET    | `/api/notifications`              | List + unread count                       |
| PATCH  | `/api/notifications/:id`          | Mark read                                 |
| POST   | `/api/notifications/mark-all-read`| Bulk mark read                            |
| GET    | `/api/health`                     | Deep-check: db, redis, chroma, gemini     |

---

## 📁 Project Structure

```
rag-knowledge-ops/
├── apps/
│   └── web/                    # Next.js App Router (auth + app route groups)
├── services/
│   ├── api/                    # FastAPI: routers, models, services, AI, retrieval
│   │   └── migrations/         # Alembic — co-located with models
│   └── worker/                 # Celery worker + Beat schedule
├── packages/
│   └── shared-types/           # OpenAPI-generated TS types (later steps)
├── infra/
│   └── docker/                 # Dockerfiles per service
├── eval/
│   └── retrieval/              # ~15 Q&A pairs + pytest harness
├── seed/                       # demo PDFs / MD / Slack / Notion JSON
├── steps/                      # phase-by-phase implementation plans (00–08)
├── .claude/
│   └── claude.md               # durable architecture context for Claude sessions
├── docker-compose.yml
├── .env.example
└── Makefile
```

---

## 🧪 Testing & Evaluation

```bash
make test        # backend pytest + frontend vitest
make test-api    # backend only (94 tests, ~17s)
make test-web    # frontend vitest (13 tests)
make eval        # RAG retrieval-quality on 15 Q&A pairs — needs GOOGLE_API_KEY
make e2e         # Playwright happy path (auth + signup→upload→ask→cite)
make coverage    # pytest --cov, --cov-fail-under=70
make lint        # ruff + ruff format --check + eslint + prettier --check + tsc --noEmit
make typecheck   # mypy on app/core, app/retrieval, app/insights
```

**Current state:** 94 backend pytest + 13 frontend vitest + 16 eval + 2 Playwright e2e = **125 tests, all green**. Backend coverage **75 %** overall, with the testable modules (`core/security`, `core/rate_limit`, `retrieval/confidence`, `retrieval/fusion`, `insights/dedup`, `services/citations`) at 93–100 %.

The **retrieval evaluation harness** lives at [`eval/retrieval/`](eval/retrieval) — a focused fixture corpus (including a *designed* conflict pair), a `questions.yaml` of 15 Q&A pairs with expected source documents and required-refusal cases, and metrics:

| Metric                          | Target | Latest run |
|---------------------------------|--------|------------|
| `recall@5`                      | ≥ 0.80 | **1.000** |
| `mrr`                           | ≥ 0.60 | **0.917** |
| `correct_refusal_rate`          | ≥ 0.90 | **1.000** |
| `expected_phrase_rate`          | ≥ 0.80 | **1.000** |

The harness:
- Ingests its corpus through the real pipeline (Postgres + Chroma + Gemini embeddings) once per session, then queries each question.
- Skips the LLM rewriter and reranker on the per-question path — saves ~30 generation calls — and budgets a small subset of `answer_question` calls for end-to-end phrase + refusal validation.
- Degrades gracefully on Gemini quota / 503: marks LLM-dependent metrics as "not measured" rather than failing.
- Prints a per-question table on every run so regressions are diagnosable without re-running.

---

## 🗺️ Roadmap

Implementation is broken into nine phase plans under [`steps/`](steps/). Each is a self-contained spec with objective, scope, data model / API contracts, edge cases, security considerations, testing plan, and acceptance criteria.

| # | Phase                                | Plan                                                                  | Status     |
|---|--------------------------------------|-----------------------------------------------------------------------|------------|
| 0 | Project understanding                | [00-project-understanding.md](steps/00-project-understanding.md)             | ✅ done |
| 1 | Architecture & setup                 | [01-architecture-and-setup.md](steps/01-architecture-and-setup.md)             | ✅ done |
| 2 | Multi-source ingestion               | [02-ingestion-pipeline.md](steps/02-ingestion-pipeline.md)                 | ✅ done |
| 3 | Retrieval & reasoning engine         | [03-retrieval-and-reasoning-engine.md](steps/03-retrieval-and-reasoning-engine.md)   | ✅ done |
| 4 | AI Copilot frontend                  | [04-ai-copilot-frontend.md](steps/04-ai-copilot-frontend.md)               | ✅ done |
| 5 | Proactive intelligence layer         | [05-proactive-intelligence-layer.md](steps/05-proactive-intelligence-layer.md)     | ✅ done |
| 6 | System design & infrastructure       | [06-system-design-infrastructure.md](steps/06-system-design-infrastructure.md)     | ✅ done |
| 7 | Testing, evaluation & quality        | [07-testing-evaluation-and-quality.md](steps/07-testing-evaluation-and-quality.md)   | ✅ done |
| 8 | Final delivery checklist             | [08-final-delivery-checklist.md](steps/08-final-delivery-checklist.md)         | ✅ done |

> **Current state:** all nine phases shipped. The system is a working end-to-end product — `docker compose up && make seed && open http://localhost:7000` puts you in front of the demo. See [`.claude/CLAUDE.md`](.claude/CLAUDE.md) for the durable architecture document used by every Claude Code session in this repo.

### Known gaps & tradeoffs

Documented in detail in [`steps/08-final-delivery-checklist.md` § 13](steps/08-final-delivery-checklist.md#13-known-gaps--tradeoffs). Headlines:

- **3 of 6 insight types ship** (conflict, repeated_decision, stale_document); the other three need a query log + larger corpus that the demo doesn't have.
- **Notifications use polling, not SSE** for the bell badge — infrastructure exists, just not wired.
- **Lighthouse a11y not formally audited.** Component-level a11y is in place; score not measured.

---

## 🛡️ Design Principles

- **Correctness over confidence.** No hallucinations. Refusal beats fabrication.
- **Background work for heavy paths.** API never blocks on LLM calls during ingestion.
- **Auth on every protected endpoint.** Workspace-scoped reads and writes — schema ready for teams.
- **Observability first.** Structured JSON logs, request IDs propagated to workers, persisted job + run history.
- **Reproducibility.** One `.env.example`, one `docker compose up`, seeded demo data.
- **No premature abstraction.** Three similar lines beat a clever helper. Don't design for hypothetical futures.

---

## 📜 License

[Apache 2.0](./LICENSE) © Yousef Ali Mansour
