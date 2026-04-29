'use client';

import Link from 'next/link';
import { use } from 'react';
import { useQuery } from '@tanstack/react-query';
import { documentsApi } from '@/lib/documents';

export default function DocumentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', id],
    queryFn: () => documentsApi.get(id),
    refetchInterval: (q) => {
      const s = q.state.data?.document.status;
      return s === 'pending' || s === 'processing' ? 2_000 : false;
    },
  });

  if (isLoading) return <div className="text-sm text-ink-muted">Loading…</div>;
  if (error || !data)
    return <div className="text-sm text-red-400">Could not load document.</div>;

  const { document: doc, chunks_preview } = data;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/documents" className="text-xs text-ink-subtle hover:text-ink">
          ← Documents
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight mt-1">{doc.title}</h1>
        <p className="text-sm text-ink-muted">
          {doc.source_type} · v{doc.version} · {doc.chunk_count} chunks ·{' '}
          <span className="text-ink-subtle">{doc.status}</span>
        </p>
        {doc.error && <p className="mt-2 text-sm text-red-400">{doc.error}</p>}
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-ink-subtle">Chunk preview</h2>
        {chunks_preview.length === 0 && (
          <p className="text-sm text-ink-muted">No chunks yet — processing pending.</p>
        )}
        {chunks_preview.map((c) => (
          <div
            key={c.id}
            className="rounded-lg border border-ink-faint bg-surface-700 p-4 shadow-card"
          >
            <div className="flex items-center justify-between text-xs text-ink-subtle mb-2">
              <span>chunk #{c.chunk_index}</span>
              {c.heading && <span className="text-ink-muted">{c.heading}</span>}
              {c.page_number != null && <span>p.{c.page_number}</span>}
            </div>
            <p className="text-sm whitespace-pre-wrap">{c.text}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
