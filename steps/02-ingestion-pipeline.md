# Step 02 — Multi-Source Knowledge Ingestion Pipeline

## Objective

Build the asynchronous ingestion pipeline that turns raw uploads (PDF, TXT, MD) and simulated external sources (Slack JSON, Notion JSON) into clean, chunked, embedded, deduplicated, versioned records — with job-status tracking surfaced to the frontend.

## User Value

Users upload knowledge from any of the supported sources and watch it become queryable. They never have to re-upload duplicates, they can re-upload an updated file and have a new version recorded, and they always know the processing status.

## Scope

- File upload endpoint (multipart) for PDF / TXT / MD.
- External-source endpoint accepting Slack and Notion-shaped JSON payloads.
- Document + chunk persistence in Postgres.
- Embedding generation via `text-embedding-004` (768d), batched, cached by chunk hash.
- Vector storage in Chroma with metadata filters.
- `tsvector` keyword index on chunk text (for hybrid search in step 03).
- Deduplication by document content hash (whole-doc) and chunk content hash (chunk-level).
- Versioning: same title + different content hash → new version, previous kept.
- Asynchronous Celery job per document; API returns 202 + job id.
- Job status endpoints + frontend polling/SSE update.

## Required Features

- Validate uploaded files: MIME sniffing (not just `Content-Type`), size limit (default 25 MB).
- Extract text:
  - PDF → `pypdf` (fast, pure-Python; fall back to `pdfminer.six` if extraction is empty).
  - TXT/MD → read directly.
  - Markdown → preserve heading structure for chunk metadata.
  - Slack JSON → flatten threads into chronologically ordered messages with author + timestamp; chunk by thread or by N-message window.
  - Notion JSON → flatten page blocks into ordered text with heading metadata.
- Normalize: collapse whitespace, strip control chars, normalize unicode (NFKC).
- Chunk: token-based with overlap. Default: 512 tokens, 64 overlap, respect heading boundaries when possible.
- Embed: batch of 32, retry on transient errors, cache by SHA-256 of chunk text.
- Store: document → chunks (Postgres) → vectors (Chroma).
- Mark job complete; emit notification "Document processed" (handled in step 05 once notifications exist; for now just persist a placeholder event).
- Trigger scoped insight generation post-ingest (wired in step 05; this step exposes the hook).

## Data Model (extends step 01)

```sql
documents (
  id              uuid pk,
  workspace_id    uuid fk workspaces.id,
  title           text not null,
  source_type     text not null check (source_type in ('pdf','txt','md','slack','notion')),
  original_filename text,
  content_hash    text not null,                  -- sha256 of normalized full text
  version         int not null default 1,         -- increments per (workspace_id, title) on content change
  status          text not null check (status in ('pending','processing','ready','failed')),
  source_metadata jsonb default '{}'::jsonb,
  chunk_count     int default 0,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now(),
  processed_at    timestamptz,
  unique (workspace_id, content_hash)             -- dedup at workspace level
);

chunks (
  id              uuid pk,
  document_id     uuid fk documents.id on delete cascade,
  chunk_index     int not null,
  text            text not null,
  text_hash       text not null,                  -- sha256 of chunk text, for embedding cache
  token_count     int,
  heading         text,
  page_number     int,
  source_timestamp timestamptz,
  embedding_id    text,                           -- chroma id (== chunks.id stringified)
  content_tsv     tsvector generated always as (to_tsvector('english', text)) stored,
  created_at      timestamptz default now()
);
create index chunks_tsv_idx on chunks using gin (content_tsv);
create index chunks_doc_idx on chunks (document_id);

ingest_jobs (
  id              uuid pk,
  document_id     uuid fk documents.id,
  status          text not null check (status in ('queued','running','succeeded','failed')),
  stage           text,                            -- extract|chunk|embed|index
  error           text,
  attempts        int default 0,
  started_at      timestamptz,
  finished_at     timestamptz,
  created_at      timestamptz default now()
);

embedding_cache (
  text_hash       text pk,
  embedding       jsonb not null,                  -- 768 floats
  model           text not null,
  created_at      timestamptz default now()
);
```

Chroma item: `id = chunks.id`, metadata = `{ document_id, workspace_id, source_type, page, heading, chunk_index, source_timestamp }`.

## API Contracts

```http
POST /api/ingest/files                       (auth, rate-limited, multipart)
  files: File[]   (one or more, total size ≤ MAX_UPLOAD_MB)
  → 202 { jobs: [{ id, document_id, status }] }

POST /api/ingest/source                      (auth, rate-limited, JSON)
Body:
  {
    "source": "slack" | "notion",
    "title": "string",
    "payload": {...}        // shape per source
  }
  → 202 { job: { id, document_id, status } }

GET /api/docs                                (auth)
Query: ?status=&source_type=&q=&cursor=&limit=
  → { items: [...], next_cursor }

GET /api/docs/:id                            (auth, workspace-scoped)
  → { document, chunks_preview: [first 5] }

GET /api/jobs/:id                            (auth)
  → { id, status, stage, error, attempts, document }

GET /api/jobs/stream                         (auth, SSE)
  Streams job state changes for the workspace; useful for upload UX.
```

## Implementation Tasks

1. **File upload router** with size/MIME validation; persist raw bytes to a temp dir, create `documents` row with status `pending`, create `ingest_jobs` row, enqueue Celery task, return 202.
2. **External-source router** for Slack/Notion JSON; same flow as files but extractor differs.
3. **Extractors** (`app/ingestion/extractors/`):
   - `pdf.py`, `text.py`, `markdown.py`, `slack.py`, `notion.py`.
   - Each returns a normalized `ExtractedDocument(text, sections=[{heading, page?, text}])`.
4. **Normalizer**: NFKC + whitespace + control-char stripping.
5. **Chunker** (`app/ingestion/chunker.py`):
   - Token-based using a tokenizer matched to embedding model (or `tiktoken`-compatible heuristic).
   - Respects section/heading boundaries — never splits mid-heading-block when possible.
   - Adds heading + page metadata to each chunk.
6. **Dedup**:
   - Whole-document: `documents.content_hash` unique per workspace. On collision: do not create new doc; if same title and same hash → return existing doc, no new job; if different title → return existing doc with a "linked under: X" note.
   - Versioning: same `(workspace_id, title)` + different `content_hash` → new doc row with `version = max+1`, status independent.
7. **Embedding service** (`app/ai/embeddings.py`): batch, retry, cache via `embedding_cache`.
8. **Indexer**: write chunks to Postgres, then upsert to Chroma in batches.
9. **Celery task `ingest_document(doc_id)`**:
   - Idempotent: if already `ready`, no-op.
   - Updates `ingest_jobs.stage` at each transition.
   - On failure: mark `failed`, persist error, retry up to 3× with exponential backoff.
   - On success: enqueue `generate_insights_scoped([doc_id])` (registered in step 05).
10. **Job-status SSE endpoint** for the frontend to react in near-real-time.
11. **Tests** (see Testing Plan).

## Edge Cases

- Empty PDF text extraction → mark failed with explicit error; suggest OCR (out of scope but messaged).
- Encrypted PDFs → fail clearly.
- Huge files near the cap → reject before reading into memory; stream to disk.
- Re-upload of identical content → 200 idempotent response with existing doc ref + "deduplicated" flag.
- Markdown with no headings → fall back to paragraph-boundary chunking.
- Slack export with no messages or only bot messages → produce a doc with chunk_count=0 and a clear status reason.
- Notion JSON with deeply nested blocks → flatten depth-first, preserve heading hierarchy in metadata.
- Concurrent uploads of the same file → DB unique constraint on content_hash + advisory lock around the create-or-fetch path.
- Embedding API rate-limited → exponential backoff, fail job after 3 attempts, surface in UI.
- Chroma down during indexing → retry; if persistent, mark job failed with `stage=index`.

## Security Considerations

- MIME sniffing via `python-magic` or `filetype` — never trust client header.
- Reject filenames with traversal characters; store under sanitized UUID-based names.
- Workspace isolation enforced at repository layer; every query filters by `workspace_id`.
- Strip embedded JS/scripts from extracted text (markdown rendered as text, not HTML).
- Cap concurrent ingestion jobs per workspace to avoid embedding-cost runaways.

## Testing Plan

- **Unit**:
  - Each extractor on representative fixtures (multi-page PDF, markdown with headings, Slack thread, Notion page).
  - Chunker: respects boundaries, overlap correct, token counts within tolerance, no chunk exceeds max.
  - Dedup logic: same hash → existing, same title diff hash → version bump.
- **Integration**:
  - Upload PDF → poll job → status `ready` → `GET /api/docs/:id` returns chunks.
  - Upload identical file twice → second is dedup-flagged.
  - Upload edited version → version becomes 2.
  - Slack JSON ingest → chunks have `source_timestamp` and author metadata.
- **Worker**:
  - Failure injection on embedding call → job retries, then fails with persisted error.
- **Performance smoke**:
  - 50-page PDF processes end-to-end under ~60s on dev hardware.

## Acceptance Criteria

- [x] `POST /api/ingest/files` accepts PDF/TXT/MD, returns 202 with job id. *(Verified live with `curl -F`. MIME sniffing via [filetype](https://pypi.org/project/filetype/); 415 on unsupported binaries.)*
- [x] `POST /api/ingest/source` accepts Slack and Notion JSON. *(Verified live; canonical shapes documented in [slack.py](../services/api/app/ingestion/extractors/slack.py) and [notion.py](../services/api/app/ingestion/extractors/notion.py).)*
- [x] Document + chunks persisted; embeddings in Chroma. *([test_ingest_service.py](../services/api/app/tests/test_ingest_service.py) walks the full pipeline with stubbed embeddings; live run reaches `stage=embed` and only stops because `GOOGLE_API_KEY` is unset, which is expected in dev.)*
- [x] Dedup prevents duplicate docs by content hash. *(Verified live: second upload of identical bytes returns `deduplicated: true`, same `document_id`, no new job.)*
- [x] Versioning increments on changed content with same title. *(Verified live: re-uploading edited content with the same filename yields `v2` while `v1` stays.)*
- [x] Job status visible via `GET /api/jobs/:id` and SSE stream. *(REST endpoint + polling-based SSE at `/api/jobs/stream/sse` consumed by the documents page.)*
- [x] All step-02 tests pass. *(33 pytest tests across normalize, chunker, extractors, dedup, ingest service, ingest API, jobs API.)*
- [x] Re-running ingestion on a `ready` doc is a no-op. *([test_ingest_orchestrator_idempotent_on_ready_doc](../services/api/app/tests/test_ingest_service.py).)*

### Hash-strategy deviation (documented)

The brief says `content_hash = sha256(normalized full text)`. We compute it
from raw upload bytes (or canonical-JSON for source payloads) at the *upload*
edge, before extraction. This makes dedup a single fast DB lookup per upload
and avoids extracting a duplicate. Trade-off: two PDFs with identical text
but different binary metadata won't dedup. Acceptable for the demo; documented
in [services/api/app/services/dedup.py](../services/api/app/services/dedup.py).

## Next

→ `steps/03-retrieval-and-reasoning-engine.md`
