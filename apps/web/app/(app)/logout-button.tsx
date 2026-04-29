'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { authApi } from '@/lib/auth';

export function LogoutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  return (
    <button
      type="button"
      disabled={pending}
      onClick={async () => {
        setPending(true);
        try {
          await authApi.logout();
        } finally {
          router.replace('/login');
          router.refresh();
        }
      }}
      className="w-full rounded-md px-3 py-2 text-left text-sm text-ink-muted hover:bg-surface-700 hover:text-ink disabled:opacity-50"
    >
      {pending ? 'Signing out…' : 'Sign out'}
    </button>
  );
}
