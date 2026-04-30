'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Calendar, Check, RefreshCw, Sparkles, X } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  insightsApi,
  type Insight,
  type InsightState,
  type Severity,
} from '@/lib/insights';

const TYPE_LABEL: Record<string, string> = {
  conflict: 'Conflict',
  repeated_decision: 'Repeated decision',
  stale_document: 'Stale document',
};

const TYPE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  conflict: AlertTriangle,
  repeated_decision: RefreshCw,
  stale_document: Calendar,
};

const SEVERITY_TONE: Record<Severity, 'danger' | 'warning' | 'muted'> = {
  high: 'danger',
  medium: 'warning',
  low: 'muted',
};

export default function InsightsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [stateFilter, setStateFilter] = useState<InsightState>('active');

  const list = useQuery({
    queryKey: ['insights', { state: stateFilter }],
    queryFn: () => insightsApi.list({ state: stateFilter }),
  });
  const runs = useQuery({ queryKey: ['insights', 'runs'], queryFn: insightsApi.runs });

  const triggerRun = useMutation({
    mutationFn: () => insightsApi.triggerRun({ scope: 'all' }),
    onSuccess: () => {
      toast.success('Run queued', 'Refresh in a few seconds to see new insights.');
      qc.invalidateQueries({ queryKey: ['insights'] });
    },
    onError: (e: Error) => toast.error('Run failed', e.message),
  });

  const patchState = useMutation({
    mutationFn: ({ id, state }: { id: string; state: InsightState }) =>
      insightsApi.patchState(id, state),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['insights'] }),
    onError: (e: Error) => toast.error('Update failed', e.message),
  });

  const items = list.data?.items ?? [];
  const lastRun = runs.data?.items?.[0];

  return (
    <div className="space-y-6 max-w-4xl">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" /> Insights
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            Proactive findings from scheduled scans of your knowledge base.
          </p>
        </div>
        <button
          type="button"
          onClick={() => triggerRun.mutate()}
          disabled={triggerRun.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-control px-3 py-2 text-sm font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${triggerRun.isPending ? 'animate-spin' : ''}`} />
          {triggerRun.isPending ? 'Queued…' : 'Run analysis'}
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <div className="inline-flex rounded-md bg-surface-700 p-1 text-xs">
          {(['active', 'read', 'dismissed'] as InsightState[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStateFilter(s)}
              className={`rounded px-3 py-1.5 transition-colors ${
                stateFilter === s ? 'bg-surface-600 text-ink' : 'text-ink-muted hover:text-ink'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        {lastRun && (
          <span className="text-xs text-ink-subtle">
            Last run · {lastRun.trigger} · {lastRun.status} · {lastRun.insights_generated} new ·{' '}
            {lastRun.insights_skipped} dedup&apos;d
          </span>
        )}
      </div>

      {list.isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}
      {list.error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          Could not load insights.
        </div>
      )}

      {!list.isLoading && items.length === 0 && (
        <div className="rounded-xl border border-dashed border-ink-faint bg-surface-700/40 p-8 text-center text-sm text-ink-muted">
          <Sparkles className="mx-auto h-5 w-5 text-accent" />
          <p className="mt-2">
            No {stateFilter} insights yet. Upload conflicting docs or click <em>Run analysis</em> to scan now.
          </p>
        </div>
      )}

      <ul className="space-y-3">
        {items.map((ins) => (
          <InsightCard
            key={ins.id}
            insight={ins}
            onDismiss={(id) => patchState.mutate({ id, state: 'dismissed' })}
            onMarkRead={(id) => patchState.mutate({ id, state: 'read' })}
            onReopen={(id) => patchState.mutate({ id, state: 'active' })}
          />
        ))}
      </ul>
    </div>
  );
}

function InsightCard({
  insight,
  onDismiss,
  onMarkRead,
  onReopen,
}: {
  insight: Insight;
  onDismiss: (id: string) => void;
  onMarkRead: (id: string) => void;
  onReopen: (id: string) => void;
}) {
  const Icon = TYPE_ICON[insight.type] ?? Sparkles;
  return (
    <li className="rounded-xl border border-ink-faint bg-surface-700 p-4 shadow-card">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-4 w-4 text-accent" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold truncate">{insight.title}</h3>
            <Badge tone="muted">{TYPE_LABEL[insight.type] ?? insight.type}</Badge>
            <Badge tone={SEVERITY_TONE[insight.severity]}>{insight.severity}</Badge>
            <span className="ml-auto text-xs text-ink-subtle">
              {new Date(insight.created_at).toLocaleString()}
            </span>
          </div>
          <p className="mt-2 text-sm text-ink-muted whitespace-pre-wrap">{insight.summary}</p>

          {insight.evidence.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {insight.evidence.map((e) => (
                <Link
                  key={e.chunk_id}
                  href={`/documents/${e.document_id}`}
                  className="inline-flex max-w-[260px] items-center gap-1 truncate rounded-md border border-ink-faint bg-surface-800 px-2 py-1 text-xs text-ink-muted hover:bg-surface-600 hover:text-ink"
                  title={e.snippet || e.title}
                >
                  <span className="truncate">{e.title}</span>
                </Link>
              ))}
            </div>
          )}

          <div className="mt-3 flex items-center gap-2 text-xs">
            {insight.state !== 'active' ? (
              <button
                type="button"
                onClick={() => onReopen(insight.id)}
                className="inline-flex items-center gap-1 rounded px-2 py-1 text-ink-muted hover:bg-surface-600 hover:text-ink"
              >
                Reopen
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => onMarkRead(insight.id)}
                  className="inline-flex items-center gap-1 rounded px-2 py-1 text-ink-muted hover:bg-surface-600 hover:text-ink"
                >
                  <Check className="h-3 w-3" /> Mark read
                </button>
                <button
                  type="button"
                  onClick={() => onDismiss(insight.id)}
                  className="inline-flex items-center gap-1 rounded px-2 py-1 text-ink-muted hover:bg-surface-600 hover:text-ink"
                >
                  <X className="h-3 w-3" /> Dismiss
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}
