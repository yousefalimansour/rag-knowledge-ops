'use client';

import Link from 'next/link';
import { useState } from 'react';
import { aiApi, type SearchResult } from '@/lib/ai';

export default function SearchPage() {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [rewrites, setRewrites] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setPending(true);
    setError(null);
    try {
      const env = await aiApi.search(q.trim());
      setResults(env.results);
      setRewrites(env.rewrites);
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
          Hybrid (vector + keyword) retrieval with RRF fusion and Gemini reranking. No LLM answer — raw chunks only.
        </p>
      </header>

      <form onSubmit={run} className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search your knowledge base"
          className="flex-1 rounded-md bg-control-input px-3 py-2 text-sm outline-none focus:border focus:border-ink"
        />
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
          Searched as: {rewrites.map((r, i) => (
            <span key={i} className="ml-1 inline-block rounded bg-surface-700 px-2 py-0.5">{r}</span>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <ul className="space-y-3">
        {results.map((r) => (
          <li key={r.chunk_id} className="rounded-xl border border-ink-faint bg-surface-700 p-4 shadow-card">
            <div className="flex items-center justify-between">
              <Link href={`/documents/${r.document_id}`} className="font-medium hover:text-accent">
                {r.title}
              </Link>
              <div className="text-xs text-ink-subtle space-x-2">
                {r.rerank_score !== null && <span>rerank {r.rerank_score.toFixed(3)}</span>}
                <span>fused {r.score.toFixed(3)}</span>
                {r.vector_rank !== null && <span>v#{r.vector_rank + 1}</span>}
                {r.keyword_rank !== null && <span>k#{r.keyword_rank + 1}</span>}
              </div>
            </div>
            {r.heading && <div className="text-xs text-ink-muted mt-0.5">{r.heading}</div>}
            <p className="mt-2 text-sm text-ink-muted whitespace-pre-wrap">{r.snippet}…</p>
          </li>
        ))}
      </ul>

      {!pending && results.length === 0 && q && !error && (
        <p className="text-sm text-ink-muted">No matches above the score threshold.</p>
      )}
    </div>
  );
}
