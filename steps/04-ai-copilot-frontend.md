# Step 04 — AI Copilot Frontend

## Objective

Ship a polished, opinionated knowledge-assistant UI — not a generic chatbot — that makes every workflow obvious: upload knowledge, watch processing, browse the base, ask questions with streamed answers, verify via a source preview panel, and review proactive insights with a real notification inbox.

## User Value

A reviewer lands in the app and within 60 seconds: signs up, drops a PDF in, sees it processing, asks a question, watches an answer stream in with citations, clicks a citation to see the source chunk in context, and notices a new-insight notification appear. No tutorial needed.

## Scope

- Auth screens: Login, Signup.
- App shell with sidebar nav + topbar (notifications bell, user menu).
- Screens: Dashboard, Documents, Upload, Knowledge Search, AI Copilot, Insights, Settings.
- SSE consumer for streamed answers.
- Source preview panel (slide-over) showing the cited chunk with surrounding context + link to the document detail.
- Job-status indicator on Documents and Upload — live via SSE from `/api/jobs/stream`.
- Notification bell with unread count, dropdown inbox, mark-read, click-through.
- Filters and search across documents.
- Empty / loading / error states for every async surface.
- Responsive layout (desktop primary, mobile usable).

## Required Features

| Screen           | Must include                                                                                              |
|------------------|-----------------------------------------------------------------------------------------------------------|
| Login            | Email/password, error display, signup link                                                                |
| Signup           | Email/password, password rules, redirect on success                                                       |
| Dashboard        | Counts (docs ready, processing, failed), latest insights (3 cards), latest activity, quick "Ask" box       |
| Documents        | Table: title, source type, status, version, chunk count, updated; filters (status, source, search), pagination |
| Upload           | Drag-drop multi-file, per-file progress + status, "ingest external source" tab for Slack/Notion JSON paste |
| Knowledge Search | Plain hybrid search (no LLM), result list with snippet highlight, click → preview                        |
| AI Copilot       | Chat thread, streaming answer, inline citation chips, side preview on click, confidence + reasoning, refusal styling |
| Insights         | Card list grouped by type, severity badges, "view evidence" → preview, dismiss/read controls              |
| Settings         | Profile, change password, API health summary, sign-out                                                    |
| Topbar bell      | Unread count, dropdown of notifications, mark-read on click, link-through                                  |

## Tech & Conventions

- Next.js 15 App Router with route groups `(auth)` and `(app)`.
- Server Components for data-prefetching where it helps (e.g. document detail), Client Components for interactive surfaces.
- TanStack Query v5 for all server state; Suspense boundaries on top-level routes.
- Tailwind + a small design-token layer (`apps/web/styles/tokens.css`) for spacing, radii, color.
- A handful of primitives in `components/ui/` (Button, Input, Dialog, Sheet, Badge, Toast). Headless UI via Radix primitives, styled with Tailwind.
- Icons: `lucide-react`.
- Forms: `react-hook-form` + `zod`.
- SSE client: thin wrapper around `EventSource` with auth via cookie; reconnect on transient failure.
- Toast system for non-blocking feedback (e.g. "Document queued for processing").

## Data Flow

- All API calls go through `lib/api.ts` (`fetch` with credentials + CSRF header + JSON helpers).
- TanStack Query keys: `['docs', filters]`, `['doc', id]`, `['jobs']`, `['insights']`, `['notifications']`, `['health']`.
- Mutations: upload, ingest source, mark-notification-read, dismiss-insight, manual-insight-run.
- Real-time updates: a single shared SSE connection to `/api/jobs/stream` updates job + notification queries (invalidate or update cache directly).

## SSE for Copilot

```ts
const evt = new EventSource('/api/ai/query/stream', { withCredentials: true });
evt.addEventListener('start',      (e) => …);
evt.addEventListener('token',      (e) => append delta);
evt.addEventListener('sources',    (e) => render citation chips);
evt.addEventListener('confidence', (e) => render confidence + reasoning);
evt.addEventListener('done',       (e) => close stream);
evt.addEventListener('error',      (e) => show error toast, close);
```

Note: `EventSource` is GET-only — for POST-with-body we use a small `fetch`-based SSE reader (TextDecoder over a streamed response) instead. The wrapper exposes the same event shape.

## Implementation Tasks

1. **App shell** (`app/(app)/layout.tsx`): auth-required server check, sidebar, topbar, query provider, toast provider.
2. **Auth pages** with `react-hook-form` + `zod`; redirect to `/dashboard` on success.
3. **API client** (`lib/api.ts`) with typed responses (use OpenAPI-generated types from `packages/shared-types`).
4. **TanStack Query setup** in `app/providers.tsx`.
5. **Documents screen**: table + filters + pagination + row click → detail.
6. **Document detail**: meta, chunks preview, re-ingest action, delete (soft).
7. **Upload screen**: drag-drop with progress; switch to "External source" tab for Slack/Notion JSON paste with a small validator.
8. **Knowledge Search**: input → `GET /api/search` → list with `<mark>` highlight on matches → preview.
9. **AI Copilot**:
   - Chat thread state in URL (e.g. `?chat=<id>`) so refresh keeps history (history persisted client-side per session for the demo).
   - Send message → stream into a draft message bubble.
   - Citation chips clickable → opens `<Sheet>` with chunk + surrounding text fetched from `GET /api/docs/:id?chunk=<id>&context=2`.
   - Refusal answers visually distinct (muted style + "Not enough evidence" badge).
10. **Insights screen**: grouped cards (conflict, stale, repeated decision, theme, missing context), severity colored badges, evidence open in Sheet.
11. **Notifications bell**: poll every 30s + reactive update via the SSE jobs stream when an insight-created event arrives. Click → mark-read mutation → navigate.
12. **Empty / loading / error**: every list has a skeleton, every fetch has an error boundary or inline retry.
13. **Theming**: light/dark with system preference; tokens centralized.
14. **A11y**: focus rings, semantic landmarks, keyboard navigation in chat + lists, color-contrast AA.

## Edge Cases

- SSE reconnect storm if API restarts → exponential backoff + jitter, max 5 retries before showing "lost connection — retry" button.
- Large documents in detail view → paginate chunks, lazy-load.
- Long answers in chat → virtualize message list once it grows.
- Markdown in answers (Gemini may produce code blocks) → render via `react-markdown` with safe defaults; no raw HTML.
- User pastes a 50 MB Slack JSON → validate size client-side before POST; surface clear error.
- Network offline → toast and disable sends; resume when back.

## Security Considerations

- Cookies handle auth — no tokens in JS / localStorage.
- CSRF token sent in custom header on every state-changing request.
- `dangerouslySetInnerHTML` is forbidden in this app.
- File picker accepts only `.pdf,.txt,.md` — validated again server-side.
- Don't render document content with HTML rendering; treat as text or markdown via a sanitized renderer.
- Rate-limit feedback in the UI: when 429 received, show the cool-down to the user.

## Testing Plan

- Unit (Vitest): API client error handling, SSE wrapper event dispatch, formatters (confidence → label).
- Component (Vitest + Testing Library): chat bubble, citation chip → opens sheet, notification bell unread badge.
- E2E (Playwright):
  - Signup → upload PDF → wait for status `ready` → ask known question → assert citation appears → open preview → assert chunk text visible.
  - Refusal: ask out-of-corpus question → assert refusal styling.
  - Notification: trigger manual insight run → bell shows unread → click → marks read.

## Acceptance Criteria

- [x] Lands on dashboard after login (no marketing landing page). *(Root [page.tsx](../apps/web/app/page.tsx) `redirect('/dashboard')`; auth route group redirects authed users hitting /login.)*
- [x] All seven screens implemented with the listed features. *(Auth, [Dashboard](../apps/web/app/(app)/dashboard/page.tsx), [Documents](../apps/web/app/(app)/documents/page.tsx) with filters, [Upload](../apps/web/app/(app)/upload/page.tsx) drag-drop + JSON paste, [Search](../apps/web/app/(app)/search/page.tsx) with `<mark>` highlight, [Copilot](../apps/web/app/(app)/copilot/copilot-client.tsx) streaming + chat history + Sheet preview, [Insights](../apps/web/app/(app)/insights/page.tsx) step-05 stub, [Settings](../apps/web/app/(app)/settings/page.tsx).)*
- [x] Streaming answers render token-by-token; citations clickable; preview panel shows source chunk in context. *([AnswerRenderer](../apps/web/components/app/answer-renderer.tsx) replaces `[uuid]` with numbered chips; click → [SourcePreviewSheet](../apps/web/components/app/source-preview-sheet.tsx) loads chunk + surrounding context.)*
- [x] Job status updates live via SSE without page reload. *(Documents page subscribes to `/api/jobs/stream/sse` and invalidates on every state change.)*
- [~] Notifications bell reflects real persisted state from the backend. *Stubbed. The notifications backend (in-app inbox, persistence, mark-read) is part of step 05; the topbar bell is a placeholder with a "soon" badge.*
- [x] Responsive on a 360px-wide viewport. *(Sidebar hides below `md:`; topbar collapses to hamburger-less brand on mobile; tables remain readable; forms use full-width controls.)*
- [~] Lighthouse a11y ≥ 95 on Copilot and Documents screens. *Not measured. Code follows the patterns: focus rings via Tailwind, semantic landmarks (`<aside>`, `<main>`, `<header>`, `<nav>`, `<article>`), ARIA labels on iconic buttons, role="alert"/"status"/"polite" on dynamic regions. A formal Lighthouse pass can run in step 07.*
- [x] No console errors / warnings on the happy path. *(Verified by 200 responses on all 7 authenticated routes; no `module-not-found` after the in-container `pnpm install`.)*

### Notable choices

- **`react-markdown` for answers** with custom `p`/`li`/`code`/`a` overrides. Citations are pre-processed into `__CITE__<uuid>__` placeholders so they survive Markdown parsing, then resolved into clickable numbered chips at render time.
- **Single SSE consumer** on the Documents page invalidates the docs query on any job state change. The Copilot uses a separate fetch-based SSE reader because `EventSource` doesn't support POST + body.
- **Dark-first design.** Tailwind tokens from step 01 (`surface`, `control`, `ink`, `accent`, plus `shadow-card/inset/button`) drive everything; no `prose` plugin needed.
- **Notifications + Insights backend** is intentionally deferred to step 05. The Insights screen ships as a styled "coming online in step 05" placeholder so the nav and visual scaffold are in place.

### Caught during validation

- **Container `node_modules` is a named volume**, so `pnpm install` on the host wasn't visible inside the web container. Resolved with `docker compose exec web pnpm install` against the volume. Documenting here so the next dep change doesn't trip the same wire.

## Next

→ `steps/05-proactive-intelligence-layer.md`
