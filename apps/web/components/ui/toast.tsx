'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { CheckCircle2, AlertTriangle, X } from 'lucide-react';
import { cn } from '@/lib/cn';

type ToastTone = 'default' | 'success' | 'error';
type Toast = { id: number; tone: ToastTone; title: string; body?: string };

type ToastApi = {
  show: (toast: Omit<Toast, 'id'>) => void;
  success: (title: string, body?: string) => void;
  error: (title: string, body?: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const show = useCallback<ToastApi['show']>(
    (toast) => {
      const id = ++idRef.current;
      setToasts((cur) => [...cur, { ...toast, id }]);
      window.setTimeout(() => remove(id), 5000);
    },
    [remove],
  );

  const api = useRef<ToastApi>({
    show,
    success: (title, body) => show({ tone: 'success', title, body }),
    error: (title, body) => show({ tone: 'error', title, body }),
  });
  // Keep `show` ref live across re-renders.
  api.current.show = show;
  api.current.success = (title, body) => show({ tone: 'success', title, body });
  api.current.error = (title, body) => show({ tone: 'error', title, body });

  return (
    <ToastContext.Provider value={api.current}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const Icon = toast.tone === 'success' ? CheckCircle2 : toast.tone === 'error' ? AlertTriangle : null;
  const ring =
    toast.tone === 'success'
      ? 'border-emerald-500/40'
      : toast.tone === 'error'
        ? 'border-red-500/40'
        : 'border-ink-faint';
  return (
    <div
      role="status"
      className={cn(
        'pointer-events-auto rounded-lg border bg-surface-800 px-3 py-2.5 text-sm shadow-card flex items-start gap-2',
        ring,
      )}
    >
      {Icon && <Icon className={cn('mt-0.5 h-4 w-4', toast.tone === 'success' ? 'text-emerald-400' : 'text-red-400')} />}
      <div className="flex-1">
        <div className="font-medium">{toast.title}</div>
        {toast.body && <div className="mt-0.5 text-xs text-ink-muted">{toast.body}</div>}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded p-0.5 text-ink-subtle hover:bg-surface-700 hover:text-ink"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
