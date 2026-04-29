'use client';

import Link from 'next/link';
import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi, type Document, type Job } from '@/lib/documents';

const STATUS_TONE: Record<Document['status'], string> = {
  pending: 'bg-surface-600 text-ink-muted',
  processing: 'bg-accent-soft text-accent border border-accent/40',
  ready: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  failed: 'bg-red-500/15 text-red-300 border border-red-500/30',
};

export default function DocumentsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentsApi.list(),
    refetchInterval: (q) => {
      // Poll while anything is in-flight; quiet when everything is done.
      const items = q.state.data?.items ?? [];
      return items.some((d: Document) => d.status === 'pending' || d.status === 'processing')
        ? 2_000
        : false;
    },
  });

  // Live job stream — invalidates the documents query whenever a job moves.
  useEffect(() => {
    const es = new EventSource('/api/jobs/stream/sse', { withCredentials: true });
    const onJob = (ev: MessageEvent) => {
      try {
        const job = JSON.parse(ev.data) as Job;
        if (job.status === 'succeeded' || job.status === 'failed' || job.status === 'running') {
          qc.invalidateQueries({ queryKey: ['documents'] });
        }
      } catch {
        // ignore malformed
      }
    };
    es.addEventListener('job', onJob as EventListener);
    return () => {
      es.removeEventListener('job', onJob as EventListener);
      es.close();
    };
  }, [qc]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Anything ingested into your workspace lives here.
          </p>
        </div>
        <Link
          href="/upload"
          className="inline-flex items-center rounded-md bg-control px-3 py-2 text-sm font-medium text-ink shadow-button hover:bg-surface-600"
        >
          Upload
        </Link>
      </header>

      <section className="rounded-xl border border-ink-faint bg-surface-700 shadow-card overflow-hidden">
        {isLoading && <div className="p-6 text-sm text-ink-muted">Loading…</div>}
        {error && <div className="p-6 text-sm text-red-400">Could not load documents.</div>}
        {data && data.items.length === 0 && (
          <div className="p-6 text-sm text-ink-muted">
            No documents yet. <Link href="/upload" className="underline hover:text-ink">Upload your first file</Link>.
          </div>
        )}
        {data && data.items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-ink-subtle">
              <tr>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Chunks</th>
                <th className="px-4 py-3 font-medium">Version</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((d) => (
                <tr key={d.id} className="border-t border-ink-faint hover:bg-surface-600/40">
                  <td className="px-4 py-3">
                    <Link href={`/documents/${d.id}`} className="font-medium hover:text-accent">
                      {d.title}
                    </Link>
                    {d.error && <div className="text-xs text-red-400 mt-1">{d.error}</div>}
                  </td>
                  <td className="px-4 py-3 text-ink-muted">{d.source_type}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs ${STATUS_TONE[d.status]}`}>
                      {d.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-muted">{d.chunk_count}</td>
                  <td className="px-4 py-3 text-ink-muted">v{d.version}</td>
                  <td className="px-4 py-3 text-ink-subtle text-xs">
                    {new Date(d.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
