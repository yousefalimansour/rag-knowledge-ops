'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Upload as UploadIcon } from 'lucide-react';
import { documentsApi, type Document, type Job } from '@/lib/documents';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusPill } from '@/components/ui/status-pill';

const SOURCE_OPTIONS = ['pdf', 'txt', 'md', 'slack', 'notion'] as const;
const STATUS_OPTIONS = ['pending', 'processing', 'ready', 'failed'] as const;

export default function DocumentsPage() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [sourceFilter, setSourceFilter] = useState<string | undefined>();
  const [search, setSearch] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', { statusFilter, sourceFilter, search }],
    queryFn: () =>
      documentsApi.list({
        status: statusFilter,
        source_type: sourceFilter,
        q: search || undefined,
      }),
    refetchInterval: (q) => {
      const items = q.state.data?.items ?? [];
      return items.some((d: Document) => d.status === 'pending' || d.status === 'processing')
        ? 2_000
        : false;
    },
  });

  useEffect(() => {
    const es = new EventSource('/api/jobs/stream/sse', { withCredentials: true });
    const onJob = (ev: MessageEvent) => {
      try {
        const job = JSON.parse(ev.data) as Job;
        if (['succeeded', 'failed', 'running'].includes(job.status)) {
          qc.invalidateQueries({ queryKey: ['documents'] });
        }
      } catch {
        /* ignore */
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
      <header className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Anything ingested into your workspace lives here.
          </p>
        </div>
        <Link
          href="/upload"
          className="inline-flex items-center gap-1.5 rounded-md bg-control px-3 py-2 text-sm font-medium text-ink shadow-button hover:bg-surface-600"
        >
          <UploadIcon className="h-3.5 w-3.5" /> Upload
        </Link>
      </header>

      <div className="flex flex-wrap gap-2 items-center">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by title…"
          aria-label="Filter by title"
          className="rounded-md bg-control-input px-3 py-1.5 text-sm outline-none focus:border focus:border-ink"
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={STATUS_OPTIONS}
        />
        <FilterSelect
          label="Type"
          value={sourceFilter}
          onChange={setSourceFilter}
          options={SOURCE_OPTIONS}
        />
        {(statusFilter || sourceFilter || search) && (
          <button
            type="button"
            className="text-xs text-ink-subtle hover:text-ink"
            onClick={() => {
              setStatusFilter(undefined);
              setSourceFilter(undefined);
              setSearch('');
            }}
          >
            Clear
          </button>
        )}
      </div>

      <section className="rounded-xl border border-ink-faint bg-surface-700 shadow-card overflow-hidden">
        {isLoading && (
          <div className="p-4 space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        )}
        {error && (
          <div className="p-6 text-sm text-red-300">Could not load documents.</div>
        )}
        {data && data.items.length === 0 && !isLoading && (
          <div className="px-6 py-12 text-center text-sm text-ink-muted">
            <FileText className="mx-auto h-6 w-6 text-ink-subtle" />
            <p className="mt-2">
              {search || statusFilter || sourceFilter
                ? 'No documents match the current filters.'
                : 'No documents yet.'}
            </p>
            {!search && !statusFilter && !sourceFilter && (
              <Link
                href="/upload"
                className="mt-3 inline-flex items-center gap-1 rounded-md bg-control px-3 py-1.5 text-xs font-medium text-ink shadow-button hover:bg-surface-600"
              >
                <UploadIcon className="h-3 w-3" /> Upload your first file
              </Link>
            )}
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
                    {d.error && <div className="text-xs text-red-300 mt-1 line-clamp-2">{d.error}</div>}
                  </td>
                  <td className="px-4 py-3 text-ink-muted">{d.source_type}</td>
                  <td className="px-4 py-3">
                    <StatusPill status={d.status} />
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

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string | undefined;
  onChange: (v: string | undefined) => void;
  options: readonly string[];
}) {
  return (
    <label className="inline-flex items-center gap-1.5 text-xs text-ink-subtle">
      <span>{label}</span>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || undefined)}
        className="rounded-md bg-control-input px-2 py-1.5 text-xs text-ink outline-none focus:border focus:border-ink"
      >
        <option value="">all</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
