'use client';

import { Search as SearchIcon } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { SourcePreviewSheet } from '@/components/app/source-preview-sheet';
import { aiApi, type SearchResult, type Source } from '@/lib/ai';
import { highlightMatches } from '@/lib/highlight';

export default function SearchPage() {
  const [q, setQ] = useState('');
  const [submittedQ, setSubmittedQ] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [rewrites, setRewrites] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewSource, setPreviewSource] = useState<Source | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setPending(true);
    setError(null);
    try {
      const env = await aiApi.search(q.trim());
      setResults(env.results);
      setRewrites(env.rewrites);
      setSubmittedQ(q.trim());
    } catch (err) {
      setError((err as Error).message || 'search failed');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge Search</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Hybrid retrieval (vector + keyword) with RRF fusion and Gemini reranking. No LLM answer — raw chunks.
        </p>
      </header>

      <form onSubmit={run} className="flex gap-2">
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search your knowledge base"
            className="w-full rounded-md bg-control-input pl-9 pr-3 py-2 text-sm outline-none focus:border focus:border-ink"
          />
        </div>
        <button
          type="submit"
          disabled={pending || !q.trim()}
          className="rounded-md bg-control px-4 py-2 text-sm font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
        >
          {pending ? 'Searching…' : 'Search'}
        </button>
      </form>

      {rewrites.length > 1 && (
        <div className="text-xs text-ink-subtle">
          Searched as:
          {rewrites.map((r, i) => (
            <Badge key={i} tone="muted" className="ml-1.5">
              {r}
            </Badge>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {pending && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {!pending && results.length === 0 && submittedQ && !error && (
        <p className="rounded-lg border border-dashed border-ink-faint p-6 text-center text-sm text-ink-muted">
          No matches above the score threshold.
        </p>
      )}

      <ul className="space-y-3">
        {results.map((r) => (
          <li
            key={r.chunk_id}
            className="rounded-xl border border-ink-faint bg-surface-700 p-4 shadow-card"
          >
            <div className="flex items-center justify-between gap-3">
              <Link href={`/documents/${r.document_id}`} className="font-medium hover:text-accent">
                {r.title}
              </Link>
              <div className="flex items-center gap-1.5 text-xs text-ink-subtle">
                {r.rerank_score !== null && <Badge tone="info">rerank {r.rerank_score.toFixed(3)}</Badge>}
                {r.vector_rank !== null && <span>v#{r.vector_rank + 1}</span>}
                {r.keyword_rank !== null && <span>k#{r.keyword_rank + 1}</span>}
              </div>
            </div>
            {r.heading && <div className="text-xs text-ink-muted mt-0.5">{r.heading}</div>}
            <p className="mt-2 text-sm text-ink-muted whitespace-pre-wrap">
              {highlightMatches(r.snippet, submittedQ)}…
            </p>
            <button
              type="button"
              onClick={() =>
                setPreviewSource({
                  document_id: r.document_id,
                  title: r.title,
                  chunk_id: r.chunk_id,
                  snippet: r.snippet,
                  score: r.rerank_score ?? r.score,
                  page: r.page,
                  heading: r.heading,
                  source_type: r.source_type,
                  chunk_index: r.chunk_index,
                })
              }
              className="mt-2 text-xs text-accent hover:underline"
            >
              Open in context
            </button>
          </li>
        ))}
      </ul>

      <SourcePreviewSheet source={previewSource} onOpenChange={(o) => !o && setPreviewSource(null)} />
    </div>
  );
}
