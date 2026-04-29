# Step 05 — Proactive Intelligence Layer

## Objective

Move beyond on-demand Q&A: build a hybrid scheduling system that automatically scans the knowledge base and surfaces high-signal insights — conflicts, recurring issues, repeated decisions, emerging themes, stale documents, missing context — categorized, severity-tagged, deduplicated, citation-backed, and persisted with full run history. Pair it with a real in-app notification system.

## User Value

A team lead opens the app on Monday and sees, without asking: "Two docs disagree about enterprise discount limits", "Support logs mention checkout-timeout 14 times this week", "Pricing policy hasn't been updated in 11 months". Each finding links to the source chunks. They get notified the moment a new high-severity insight appears.

## Scope

- Insight generation engine (Celery tasks):
  - `generate_insights_scoped(doc_ids)` — triggered post-ingest by step 02's hook.
  - `coordinator_30m` — Celery Beat every 30 min; scans changed/unprocessed knowledge since last successful run; enqueues scoped jobs.
  - `nightly_audit` — Celery Beat every night at 03:00; full cross-document analysis.
  - `manual_run(scope)` — triggered by `POST /api/insights/run`.
- Persisted run history with status, errors, scope, and source citations.
- Insight deduplication via `dedup_hash` unique index.
- In-app notification system: persisted, bell UI feed, read/unread, severity, source links.
- Endpoints: list/get insights, run manually, dismiss/mark-read insight, list/mark-read notifications.

## Required Insight Types

| Type                | Trigger                                      | Severity hint              |
|---------------------|----------------------------------------------|----------------------------|
| `conflict`          | Two chunks make contradictory claims         | high                       |
| `frequent_issue`    | Theme repeats across many support-log chunks | medium / high by frequency |
| `repeated_decision` | Same decision appears in ≥ 2 docs            | low / medium               |
| `emerging_theme`    | Topic surges in recent ingestion window      | medium                     |
| `stale_document`    | Doc not updated for > N days, still cited    | low / medium               |
| `missing_context`   | Frequent questions return weak evidence      | medium                     |

## Data Model (extends earlier steps)

```sql
insights (
  id           uuid pk,
  workspace_id uuid fk workspaces.id,
  type         text not null,                -- 'conflict' | 'frequent_issue' | ...
  title        text not null,
  summary      text not null,
  severity     text not null check (severity in ('low','medium','high')),
  confidence   float,                        -- 0..1
  evidence     jsonb not null,               -- [{document_id, chunk_id, snippet, score}]
  dedup_hash   text not null unique,         -- sha256(type + sorted source ids + normalized title)
  state        text not null default 'active' check (state in ('active','dismissed','read')),
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);
create index insights_ws_state_idx on insights (workspace_id, state, created_at desc);

insight_runs (
  id                 uuid pk,
  workspace_id       uuid fk workspaces.id,
  scope              text not null,                -- 'post_ingest:<doc_ids>' | 'coordinator' | 'nightly' | 'manual:<spec>'
  trigger            text not null check (trigger in ('post_ingest','coordinator','nightly','manual')),
  status             text not null check (status in ('queued','running','succeeded','failed')),
  error              text,
  source_doc_ids     jsonb default '[]'::jsonb,
  insights_generated int default 0,
  insights_skipped   int default 0,                -- duplicates collapsed via dedup_hash
  watermark_after    timestamptz,                  -- for coordinator: max(updated_at) processed
  started_at         timestamptz,
  finished_at        timestamptz
);

notifications (
  id          uuid pk,
  user_id     uuid fk users.id,
  workspace_id uuid fk workspaces.id,
  type        text not null,                       -- 'insight_created' | 'ingest_completed' | 'ingest_failed'
  title       text not null,
  body        text,
  severity    text check (severity in ('low','medium','high','info')),
  link_kind   text,                                -- 'insight' | 'document'
  link_id     uuid,
  read_at     timestamptz,
  created_at  timestamptz default now()
);
create index notifications_user_unread_idx on notifications (user_id, read_at, created_at desc);
```

## API Contracts

```http
GET /api/ai/insights                          (auth)
Query: ?type=&severity=&state=&cursor=&limit=
  → { items: [...], next_cursor }

GET /api/ai/insights/:id                      (auth, workspace-scoped)
  → { insight, runs: [...], related_documents: [...] }

PATCH /api/ai/insights/:id                    (auth)
Body: { "state": "dismissed" | "read" | "active" }

POST /api/insights/run                        (auth, rate-limited, admin/owner only for now)
Body:
  {
    "scope": "all" | "documents" | "type",
    "document_ids": ["..."],         // when scope=documents
    "type": "conflict" | ...         // when scope=type
  }
  → 202 { run_id }

GET /api/insights/runs                        (auth)
  → list of recent runs (status, scope, counts, timing)

GET /api/notifications                        (auth)
Query: ?unread=true|false&cursor=&limit=
  → { items: [...], next_cursor, unread_count }

PATCH /api/notifications/:id                  (auth)
Body: { "read_at": "now" }

POST /api/notifications/mark-all-read         (auth)
```

## Generation Strategies (per insight type)

- **conflict**: cluster recent chunks by topic embedding (KMeans/HDBSCAN); within each cluster, ask Gemini "Are any of these statements in conflict? If yes, return JSON `{title, summary, evidence: [chunk_ids]}` else `null`."
- **frequent_issue**: count topic-cluster size in recent ingestion window weighted by source type (support logs > docs); above threshold → produce insight.
- **repeated_decision**: extract decision-like sentences (heuristic + LLM verification) → cluster by similarity → if a decision appears in ≥ 2 distinct documents, surface.
- **emerging_theme**: compare topic-cluster sizes in last-7-days vs prior baseline; significant spike → surface.
- **stale_document**: documents with `updated_at` older than threshold (e.g. 180 days) AND referenced in recent retrieval logs (so we know it's still being read) → surface.
- **missing_context**: from query logs, find questions that returned `confidence < 0.25` repeatedly → suggest "missing context: <topic>" insight.

> The scheduled task **enqueues scoped worker jobs**; it does not perform heavy LLM work directly. The coordinator's responsibility is selection + enqueue.

## Implementation Tasks

1. **Migrations** for `insights`, `insight_runs`, `notifications`.
2. **Run-record helpers**: open/close `insight_runs` with stage transitions; persist errors with traceback.
3. **Scoped generator** (`app/insights/scoped.py`):
   - Inputs: list of doc ids.
   - Build a small candidate set (the doc's chunks + N most-similar chunks from existing docs).
   - Generate conflict + repeated-decision + missing-context insights for that slice.
   - Compute `dedup_hash`; on collision → skip with `insights_skipped++`.
4. **Coordinator** (`app/insights/coordinator.py`):
   - Read `watermark_after` of last successful coordinator run.
   - Find documents with `updated_at > watermark`.
   - Enqueue `generate_insights_scoped(doc_ids)` per batch.
   - Update watermark on success.
5. **Nightly audit** (`app/insights/nightly.py`):
   - Cluster all chunks (or a sample if very large) via HDBSCAN over embeddings.
   - For each cluster: run conflict + emerging-theme + repeated-decision generators.
   - Run stale-document scan over the document table.
   - Run missing-context scan over the last 24h of low-confidence queries.
6. **Manual trigger** endpoint enqueues the appropriate generator.
7. **Notification dispatcher** (`app/notifications/dispatcher.py`):
   - On insight create with severity ≥ medium → create one notification per workspace member.
   - On ingest completion / failure → create a notification for the uploader.
   - SSE channel `/api/jobs/stream` (extended from step 02) emits notification events too — no separate connection.
8. **Beat schedule** (`services/worker/app/beat_schedule.py`):
   - `INSIGHT_COORDINATOR_CRON` (default `*/30 * * * *`) → coordinator task.
   - `INSIGHT_NIGHTLY_AUDIT_CRON` (default `0 3 * * *`) → nightly task.
9. **Logging**: every run logs `insight_run_id`, scope, watermark, counts.
10. **Tests** (see Testing Plan).

## Edge Cases

- Two simultaneous runs on the same doc → DB advisory lock keyed by `workspace_id + scope-key` to serialize.
- Empty knowledge base → coordinator and nightly are no-ops with status `succeeded`, counts 0.
- Gemini returns malformed JSON → strict JSON-mode prompts + retry once + on second failure mark run failed with parse error.
- Insight passes dedup but evidence chunks were since deleted → invalidate insight (state `dismissed`, reason `evidence_removed`).
- Notification flood (e.g. 50 insights from a nightly run) → bundle into one digest notification when count > threshold.
- Stale-document detection on a brand-new workspace with old seed data → `created_at` overrides `updated_at` for staleness.
- Coordinator falling behind (last watermark very old) → bound the catch-up batch to N docs per run.

## Security Considerations

- Workspace isolation: every query filters by `workspace_id`; tasks receive `workspace_id` and assert it on every read.
- `POST /api/insights/run` rate-limited (1/min/user) and restricted to workspace owner.
- Evidence stored as references (ids + snippets), never as full document text in `insights.evidence`.
- Notifications never include secret/full-document content — title + summary only.
- Beat schedule cron expressions validated at boot; misconfigured cron raises a clear startup error.

## Testing Plan

- **Unit**:
  - Dedup hash stability across input order.
  - Coordinator watermark advance is monotonic.
  - Notification digest collapses correctly above threshold.
- **Integration**:
  - Ingest a fixture pair of docs that conflict on a known fact → run scoped generator → assert one `conflict` insight with both doc ids in evidence.
  - Ingest a doc, idle, run coordinator → expect no work (already covered post-ingest).
  - Run nightly on a fixture corpus → expect ≥ 1 of each major type or graceful empty.
  - Manual run with scope=documents enqueues correctly and persists run record.
- **Worker**:
  - Failure injection in Gemini call → run record marked failed with error text.
- **API**:
  - List/filter/pagination correct; PATCH state transitions valid.
  - Notifications: list, unread count, mark-read, mark-all-read all correct.

## Acceptance Criteria

- [ ] Post-ingest scoped insight task fires automatically after each successful ingestion.
- [ ] Coordinator runs every 30 min and only processes deltas.
- [ ] Nightly audit runs and produces cross-document insights on the seeded corpus.
- [ ] `POST /api/insights/run` triggers a manual run; status visible in `/api/insights/runs`.
- [ ] Insights deduplicated via `dedup_hash` — re-running produces no duplicates.
- [ ] Each insight links to evidence chunks; clicking from UI opens the source preview.
- [ ] Notifications persist, show unread count, can be marked read.
- [ ] Bell UI receives a real notification when a new high-severity insight is created.

## Next

→ `steps/06-system-design-infrastructure.md`
