'use client';

import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/auth';

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Skeleton view. Real metrics, recent activity, and insights land in later steps.
        </p>
      </header>

      <section className="rounded-xl border border-ink-faint bg-surface-700 p-6 shadow-card">
        <h2 className="text-sm font-medium text-ink-subtle">Signed in as</h2>
        {isLoading && <p className="mt-2 text-sm text-ink-muted">Loading…</p>}
        {error && <p className="mt-2 text-sm text-red-400">Could not load session.</p>}
        {data && (
          <dl className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            <div>
              <dt className="text-ink-subtle">Email</dt>
              <dd className="font-medium">{data.user.email}</dd>
            </div>
            <div>
              <dt className="text-ink-subtle">Workspace</dt>
              <dd className="font-medium">{data.workspace.name}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="rounded-xl border border-dashed border-ink-faint p-6 text-sm text-ink-muted">
        Up next: upload (step&nbsp;02), copilot streaming (step&nbsp;04), insights (step&nbsp;05).
      </section>
    </div>
  );
}
