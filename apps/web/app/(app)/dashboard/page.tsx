'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { ArrowRight, FileText, MessageSquare, Sparkles, Upload } from 'lucide-react';
import { authApi } from '@/lib/auth';
import { documentsApi } from '@/lib/documents';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusPill } from '@/components/ui/status-pill';

export default function DashboardPage() {
  const router = useRouter();
  const me = useQuery({ queryKey: ['auth', 'me'], queryFn: authApi.me });
  const docs = useQuery({ queryKey: ['documents'], queryFn: () => documentsApi.list() });
  const [question, setQuestion] = useState('');

  const items = docs.data?.items ?? [];
  const counts = {
    ready: items.filter((d) => d.status === 'ready').length,
    processing: items.filter((d) => d.status === 'processing' || d.status === 'pending').length,
    failed: items.filter((d) => d.status === 'failed').length,
  };
  const recent = items.slice(0, 5);

  function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    router.push(`/copilot?q=${encodeURIComponent(question.trim())}`);
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {me.data
            ? `Welcome back. You're working in ${me.data.workspace.name}.`
            : 'Welcome back.'}
        </p>
      </header>

      <section aria-label="Quick ask" className="rounded-xl border border-ink-faint bg-surface-700 p-5 shadow-card">
        <h2 className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Quick ask</h2>
        <form onSubmit={ask} className="mt-3 flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask anything about your workspace…"
            className="flex-1 rounded-md bg-control-input px-3 py-2 text-sm outline-none focus:border focus:border-ink"
          />
          <button
            type="submit"
            disabled={!question.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-control px-3 py-2 text-sm font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
          >
            <MessageSquare className="h-3.5 w-3.5" /> Ask
          </button>
        </form>
        <p className="mt-2 text-xs text-ink-subtle">Streamed answer with cited sources.</p>
      </section>

      <section aria-label="Knowledge base counts" className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <CountCard label="Ready" value={counts.ready} loading={docs.isLoading} tone="success" />
        <CountCard label="Processing" value={counts.processing} loading={docs.isLoading} tone="info" />
        <CountCard label="Failed" value={counts.failed} loading={docs.isLoading} tone="danger" />
      </section>

      <section aria-label="Recent documents" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-ink-subtle">Recent documents</h2>
          <Link
            href="/documents"
            className="text-xs text-ink-muted hover:text-ink inline-flex items-center gap-1"
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="rounded-xl border border-ink-faint bg-surface-700 shadow-card overflow-hidden">
          {docs.isLoading ? (
            <div className="p-4 space-y-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : recent.length === 0 ? (
            <EmptyState />
          ) : (
            <ul className="divide-y divide-ink-faint">
              {recent.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <Link href={`/documents/${d.id}`} className="min-w-0 flex-1 truncate hover:text-accent">
                    <div className="text-sm font-medium truncate">{d.title}</div>
                    <div className="text-xs text-ink-subtle">
                      {d.source_type} · v{d.version} · {d.chunk_count} chunks
                    </div>
                  </Link>
                  <StatusPill status={d.status} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section aria-label="Insights teaser" className="rounded-xl border border-dashed border-ink-faint p-5 text-sm text-ink-muted flex items-center gap-3">
        <Sparkles className="h-4 w-4 text-accent" />
        Proactive insights (conflicts, stale docs, recurring decisions) come online in step&nbsp;05.
      </section>
    </div>
  );
}

function CountCard({
  label,
  value,
  loading,
  tone,
}: {
  label: string;
  value: number;
  loading: boolean;
  tone: 'success' | 'info' | 'danger';
}) {
  const accent =
    tone === 'success'
      ? 'text-emerald-300'
      : tone === 'info'
        ? 'text-accent'
        : 'text-red-300';
  return (
    <div className="rounded-xl border border-ink-faint bg-surface-700 p-4 shadow-card">
      <div className="text-xs uppercase tracking-wide text-ink-subtle">{label}</div>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-12" />
      ) : (
        <div className={`mt-2 text-2xl font-semibold ${accent}`}>{value}</div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="px-4 py-8 text-center text-sm text-ink-muted">
      <FileText className="mx-auto h-5 w-5 text-ink-subtle" />
      <p className="mt-2">No documents yet.</p>
      <Link
        href="/upload"
        className="mt-3 inline-flex items-center gap-1 rounded-md bg-control px-3 py-1.5 text-xs font-medium text-ink shadow-button hover:bg-surface-600"
      >
        <Upload className="h-3 w-3" /> Upload your first file
      </Link>
    </div>
  );
}
