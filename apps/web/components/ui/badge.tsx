import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type Tone = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'muted';

const TONE_STYLES: Record<Tone, string> = {
  default: 'bg-surface-600 text-ink',
  success: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  warning: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  danger: 'bg-red-500/15 text-red-300 border border-red-500/30',
  info: 'bg-accent-soft text-accent border border-accent/40',
  muted: 'bg-surface-700 text-ink-subtle border border-ink-faint',
};

export function Badge({
  tone = 'default',
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        TONE_STYLES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
