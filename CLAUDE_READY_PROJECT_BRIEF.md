# Claude-Ready Project Brief: AI Knowledge Operations System

Copy everything below into Claude.

---

# Master Instruction For Claude

You are the lead full-stack engineer and technical planner for a new project called **AI Knowledge Operations System**.

Your job is to understand the product deeply, create a clear implementation plan, prepare project documentation, then build the system step by step using current best practices as of 2026.

Important: Every item labeled as "bonus" in the original challenge must be treated as mandatory scope. Do not treat any bonus feature as optional.

Before writing production code, you must first create the project planning and context files described below.

## 1. First Actions Required

Before implementation, do the following in order:

1. Read this full brief carefully.
2. Inspect the existing repository, if one exists.
3. Identify the current stack, package manager, folder structure, and existing conventions.
4. If the repository is empty, create a clean project structure from scratch.
5. Verify current 2026 best practices using official documentation for the selected technologies when needed.
6. Do not use outdated patterns if a newer stable and recommended approach exists.
7. Create a `.claude/claude.md` file that explains the project, architecture, rules, commands, and implementation expectations.
8. Create a `steps/` folder.
9. Inside `steps/`, create a separate detailed planning file for each major project phase.
10. Only after the planning files exist, begin implementation step by step.

## 2. Project Summary

Build an **AI Knowledge Operations System** for modern teams that are overwhelmed by scattered information.

The system must:

- Ingest knowledge from multiple sources.
- Extract, clean, chunk, embed, and store information.
- Make the knowledge base searchable through semantic and keyword search.
- Let users ask natural language questions and receive accurate answers with cited sources.
- Provide a polished AI copilot interface, not just a basic chatbot.
- Proactively scan the knowledge base and surface useful insights.
- Be designed like a real production product with modular architecture, background jobs, Docker setup, logging, error handling, rate limiting, caching, and tests.

## 3. Business Context

Modern companies store important information across many places:

- PDFs
- Markdown files
- Text documents
- Notion pages
- Slack conversations
- Meeting notes
- Support logs
- Dashboards
- Internal decisions

Important knowledge is often lost, duplicated, outdated, or hard to retrieve.

This project solves that by turning raw documents and conversations into searchable, structured intelligence.

## 4. Recommended Product Name

Use one of these names unless the repository already has a name:

- KnowledgeOps AI
- InsightOps
- ContextHub AI
- TeamMemory AI

Prefer **KnowledgeOps AI** if no better name exists.

## 5. Recommended Tech Stack

Use the best available stable versions and practices as of 2026.

Recommended stack:

- Frontend: Next.js App Router, React, TypeScript, TailwindCSS
- Frontend data layer: TanStack Query or SWR
- Backend: FastAPI with Python
- Database: PostgreSQL
- Vector database: Chroma
- Background jobs: Redis plus a worker system such as Celery
- AI provider: google ai studio
- File processing: PDF, TXT, MD support
- Infrastructure: Docker Compose
- Testing: backend unit/integration tests, frontend tests, and at least a small retrieval quality evaluation dataset

If starting from an empty repo, prefer:

- Next.js App Router frontend
- FastAPI backend
- PostgreSQL
- Chroma for vector search
- Redis plus a worker Celery for background jobs
- Docker Compose if needed 

## 6. Mandatory Documentation Files

Create this file:

```text
.claude/claude.md
```

It must include:

- Project name and mission
- Product goals
- Technical architecture
- Selected tech stack and reasons
- Folder structure
- Backend responsibilities
- Frontend responsibilities
- Worker responsibilities
- AI/retrieval pipeline responsibilities
- Database and vector database responsibilities
- Environment variables
- Local development commands
- Testing commands
- Coding conventions
- Security rules
- Error handling rules
- Logging and observability rules
- Definition of done
- List of all mandatory features
- Reminder that all original bonus items are required

Create this folder:

```text
steps/
```

Inside `steps/`, create these planning files before implementation:

```text
steps/00-project-understanding.md
steps/01-architecture-and-setup.md
steps/02-ingestion-pipeline.md
steps/03-retrieval-and-reasoning-engine.md
steps/04-ai-copilot-frontend.md
steps/05-proactive-intelligence-layer.md
steps/06-system-design-infrastructure.md
steps/07-testing-evaluation-and-quality.md
steps/08-final-delivery-checklist.md
```

Each planning file must include:

- Objective
- User value
- Scope
- Required features
- Data model or API contracts where relevant
- Step-by-step implementation tasks
- Edge cases
- Security considerations
- Testing plan
- Acceptance criteria

## 7. Step 1: Multi-Source Knowledge Ingestion

Build backend ingestion for multiple knowledge sources.

Required source types:

- `.pdf`
- `.txt`
- `.md`
- Simulated Slack data as JSON
- Simulated Notion data as JSON

Required processing:

- File upload validation
- Text extraction
- Content normalization
- Chunking
- Metadata extraction
- Embedding generation
- Storage of original document records
- Storage of chunks
- Storage of vector embeddings
- Deduplication
- Document versioning
- Background ingestion jobs
- Job status tracking
- Error reporting for failed ingestion

Required endpoints:

```http
POST /api/ingest/files
POST /api/ingest/source
GET /api/docs
GET /api/docs/:id
```

Suggested document metadata:

- id
- title
- source type
- original file name
- content hash
- version
- status
- created at
- updated at
- processed at
- chunk count
- source-specific metadata

Suggested chunk metadata:

- id
- document id
- chunk index
- text
- token count
- heading or section
- page number when available
- source timestamp when available
- embedding id
- created at

Ingestion must be asynchronous for heavy processing. The API should accept the request, create records, enqueue jobs, and allow the frontend to show processing status.

## 8. Step 2: Retrieval And Reasoning Engine

Build a retrieval-augmented generation system.

Required endpoint:

```http
POST /api/ai/query
```

Required input:

```json
{
  "question": "What decisions were made about product pricing last week?"
}
```

Required output:

```json
{
  "answer": "Clear answer grounded in retrieved context.",
  "sources": [
    {
      "document_id": "doc_123",
      "title": "Pricing Meeting Notes",
      "chunk_id": "chunk_456",
      "snippet": "Relevant quoted or summarized context",
      "score": 0.87
    }
  ],
  "confidence": 0.91,
  "reasoning": "Short user-facing reasoning summary, not hidden chain-of-thought."
}
```

Required retrieval capabilities:

- Semantic vector search
- Keyword search
- Hybrid search combining semantic and keyword results
- Query rewriting
- Multi-step retrieval when useful
- Re-ranking
- Filtering by document/source/date/type when available
- Source citation
- Confidence scoring
- Ambiguity handling
- Clear fallback when there is not enough evidence

Important AI behavior:

- Do not hallucinate.
- Always ground answers in retrieved sources.
- Cite sources clearly.
- If the system does not know, say so.
- If the question is ambiguous, ask a clarifying question or explain the ambiguity.
- Keep internal chain-of-thought private.
- Provide a concise reasoning summary only when useful.

## 9. Step 3: AI Copilot Frontend

Build a polished knowledge assistant UI, not just a chatbot.

Required frontend features:

- Upload documents
- Manage documents
- View document processing status
- View processed knowledge base
- Search and filter documents
- Ask questions through a chat-style interface
- Show streaming answer generation if supported by the backend
- Show answer citations
- Show source snippets
- Show a source preview panel
- Show confidence score
- Show ambiguity or missing-evidence states
- Show ingestion job progress and failures
- Provide clean empty states and loading states
- Provide responsive layout for desktop and mobile

Recommended main screens:

- Dashboard
- Documents
- Upload
- Knowledge Search
- AI Copilot
- Insights
- Settings or API status

UX expectations:

- Clean and professional
- Fast to understand
- Designed for work, not marketing
- Uses consistent spacing, typography, and controls
- Avoids decorative clutter
- Makes sources easy to verify
- Makes document status obvious
- Makes failed jobs recoverable

## 10. Step 4: Proactive Intelligence Layer

Move beyond Q&A. Build AI that proactively surfaces insights.

Required endpoint:

```http
GET /api/ai/insights
```

Required behavior:

- Periodically scan the knowledge base.
- Generate useful insights.
- Categorize insights.
- Store insights.
- Expose insights to the frontend.
- Show when each insight was generated.
- Link insights back to source documents and chunks.

Required insight types:

- Frequent issues mentioned in support logs
- Repeated decisions across teams
- Conflicting information detected
- Emerging themes
- Stale or outdated documents
- Missing context or incomplete information

Required advanced behavior:

- Scheduled jobs
- Insight categorization
- Mock notifications
- Insight severity or priority
- Dismissed/read state
- Evidence citations for every insight

Example insight:

```json
{
  "id": "insight_123",
  "type": "conflict",
  "title": "Conflicting pricing policy found",
  "summary": "Two documents mention different discount limits for enterprise customers.",
  "severity": "high",
  "sources": ["doc_1", "doc_2"],
  "created_at": "2026-04-29T10:00:00Z"
}
```

## 11. Step 5: System Design And Infrastructure

Design and implement the system like a real product.

Required infrastructure:

- Docker Compose setup
- Separate frontend service
- Separate API service
- Separate worker service
- PostgreSQL service
- Vector database service when applicable
- Redis service for queues/cache
- Environment variable examples
- Clear local setup instructions

Required engineering quality:

- Modular architecture
- Typed API contracts
- Validation at API boundaries
- Centralized error handling
- Structured logging
- Request IDs or correlation IDs
- Rate limiting
- Caching where useful
- Secure secret handling
- File upload limits
- MIME/type validation
- CORS configuration
- Health check endpoints
- API documentation
- Database migrations
- Seed/demo data

Required testing:

- Unit tests for chunking and parsing
- Unit tests for retrieval logic
- API integration tests
- Worker/job tests
- Frontend component or flow tests
- Retrieval quality evaluation examples
- At least one end-to-end demo flow

## 12. Suggested Architecture

Use a modular architecture similar to this:

```text
apps/
  web/
    app/
    components/
    lib/
    hooks/
    styles/

services/
  api/
    app/
      main.py
      api/
      core/
      db/
      models/
      schemas/
      services/
      repositories/
      workers/
      ai/
      ingestion/
      retrieval/
      insights/
      tests/

infra/
  docker/
  migrations/

steps/

.claude/
```

If the selected framework prefers a different structure, adapt it while keeping the same separation of concerns.

## 13. API Requirements Summary

Implement these endpoints:

```http
POST /api/ingest/files
POST /api/ingest/source
GET /api/docs
GET /api/docs/:id
POST /api/ai/query
GET /api/ai/insights
GET /api/health
```

Add supporting endpoints if needed:

```http
GET /api/jobs/:id
GET /api/search
POST /api/ai/query/stream
POST /api/insights/run
PATCH /api/ai/insights/:id
```

## 14. Frontend Quality Bar

The frontend must feel like a real product demo for a hiring challenge.

Do not build a generic landing page as the primary experience. The first screen should be the actual application dashboard.

The interface should make these workflows obvious:

1. Upload knowledge.
2. Watch processing status.
3. Browse the knowledge base.
4. Ask a question.
5. Verify the answer through sources.
6. Review proactive insights.

## 15. AI And Retrieval Quality Bar

The AI system must prioritize correctness over sounding confident.

The answer should:

- Use only retrieved evidence.
- Cite sources.
- Explain uncertainty.
- Avoid unsupported claims.
- Handle conflicting sources.
- Show confidence based on retrieval strength and source agreement.

Build a small evaluation set with sample questions and expected source documents.

## 16. Deliverables

By the end, the repository should contain:

- Working frontend
- Working backend
- Working worker/background jobs
- Database schema and migrations
- Vector search setup
- File ingestion
- Simulated Slack/Notion ingestion
- RAG query endpoint
- Proactive insights endpoint
- Docker Compose setup
- README with setup instructions
- `.env.example`
- `.claude/claude.md`
- `steps/` folder with all planning files
- Tests
- Demo data
- Final delivery checklist

## 17. Definition Of Done

The project is done only when:

- All required endpoints work.
- PDF, TXT, MD, Slack JSON, and Notion JSON ingestion work.
- Background ingestion jobs work.
- Deduplication works.
- Document versioning works.
- Vector embeddings are stored and searchable.
- Hybrid search works.
- Query rewriting and reranking exist.
- AI answers cite sources.
- Confidence scores are returned.
- Ambiguous and unknown questions are handled safely.
- Frontend can upload, browse, search, ask, and inspect sources.
- Streaming responses are implemented or clearly supported by a streaming endpoint.
- Proactive insights are generated and displayed.
- Scheduled insight generation exists.
- Mock notifications exist.
- Docker Compose can run the project locally.
- Logging, error handling, caching, and rate limiting exist.
- Tests cover the critical path.
- README explains how to run and test everything.
- `.claude/claude.md` explains the project for future Claude sessions.
- `steps/` contains detailed step plans.

## 18. Working Style

Work carefully and visibly.

For each major step:

1. Update or create the relevant file inside `steps/`.
2. Implement the step.
3. Add or update tests.
4. Run the relevant checks.
5. Update documentation.
6. Move to the next step.

If tradeoffs are needed, document them in the relevant step file.

If something cannot be completed, document:

- What is missing
- Why it is blocked
- What should be done next

## 19. Original Challenge Requirements, Cleaned

The hiring challenge asks for an AI Knowledge Operations System.

The mission is to build a full-stack product that ingests team knowledge from files and simulated external sources, turns it into searchable intelligence, lets users ask questions with grounded AI answers, and proactively generates insights from the stored knowledge.

The company is looking for a founding-style full-stack engineer who can demonstrate backend fundamentals, system design, AI integration, product thinking, and clean execution.

This project should demonstrate:

- Full-stack engineering
- API design
- Database design
- Vector search
- Retrieval-augmented generation
- Background processing
- AI product UX
- System design
- Dockerized infrastructure
- Observability
- Testing
- Ownership

Build it as if it will be reviewed by senior engineers who care about correctness, clarity, architecture, and product quality.

