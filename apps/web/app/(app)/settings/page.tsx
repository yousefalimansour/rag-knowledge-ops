'use client';

import { LogOut, ShieldCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/auth';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

type Health = { status: string; db: string; redis: string; chroma: string; gemini: string };

async function fetchHealth(): Promise<Health> {
  const res = await fetch('/api/health', { credentials: 'include' });
  if (!res.ok) throw new Error('health fetch failed');
  return res.json();
}

export default function SettingsPage() {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const me = useQuery({ queryKey: ['auth', 'me'], queryFn: authApi.me });
  const health = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });

  async function logout() {
    setSigningOut(true);
    try {
      await authApi.logout();
    } finally {
      router.replace('/login');
      router.refresh();
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-ink-muted">Profile, system status, and sign-out.</p>
      </header>

      <section className="rounded-xl border border-ink-faint bg-surface-700 p-5 shadow-card space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Profile</h2>
        {me.isLoading && <Skeleton className="h-12 w-full" />}
        {me.data && (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            <div>
              <dt className="text-ink-subtle text-xs">Email</dt>
              <dd className="font-medium">{me.data.user.email}</dd>
            </div>
            <div>
              <dt className="text-ink-subtle text-xs">Workspace</dt>
              <dd className="font-medium">{me.data.workspace.name}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-ink-subtle text-xs">Member since</dt>
              <dd>{new Date(me.data.user.created_at).toLocaleString()}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="rounded-xl border border-ink-faint bg-surface-700 p-5 shadow-card space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-ink-subtle flex items-center gap-2">
          <ShieldCheck className="h-3.5 w-3.5" /> System status
        </h2>
        {health.isLoading && <Skeleton className="h-12 w-full" />}
        {health.data && (
          <ul className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-sm">
            <HealthRow label="Overall" value={health.data.status} />
            <HealthRow label="Database" value={health.data.db} />
            <HealthRow label="Redis" value={health.data.redis} />
            <HealthRow label="Chroma" value={health.data.chroma} />
            <HealthRow label="Gemini" value={health.data.gemini} />
          </ul>
        )}
        {health.error && (
          <p className="text-xs text-red-300">Could not reach /api/health.</p>
        )}
      </section>

      <section className="rounded-xl border border-ink-faint bg-surface-700 p-5 shadow-card">
        <h2 className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Session</h2>
        <button
          type="button"
          onClick={() => void logout()}
          disabled={signingOut}
          className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-control px-3 py-1.5 text-sm font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
        >
          <LogOut className="h-3.5 w-3.5" />
          {signingOut ? 'Signing out…' : 'Sign out'}
        </button>
      </section>

      <p className="text-xs text-ink-subtle">
        Password change UI lands in step&nbsp;05 alongside the notifications inbox.
      </p>
    </div>
  );
}

function HealthRow({ label, value }: { label: string; value: string }) {
  const tone =
    value === 'ok' ? 'success' : value === 'unknown' ? 'muted' : value === 'degraded' ? 'warning' : 'danger';
  return (
    <li className="rounded-md border border-ink-faint bg-surface-800 px-3 py-2">
      <div className="text-xs text-ink-subtle">{label}</div>
      <div className="mt-1">
        <Badge tone={tone}>{value}</Badge>
      </div>
    </li>
  );
}
