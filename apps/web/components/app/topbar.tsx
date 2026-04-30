'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Bell, ChevronDown, LogOut, Settings, User } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/auth';
import { NotificationsBell } from './notifications-bell';

export function Topbar() {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const { data } = useQuery({ queryKey: ['auth', 'me'], queryFn: authApi.me });

  async function onLogout() {
    setSigningOut(true);
    try {
      await authApi.logout();
    } finally {
      router.replace('/login');
      router.refresh();
    }
  }

  const initials = data?.user.email ? data.user.email[0]?.toUpperCase() : '?';

  return (
    <header className="flex items-center justify-between gap-4 border-b border-ink-faint bg-surface-800 px-4 md:px-6 py-3">
      <div className="md:hidden flex items-center gap-2 text-sm font-semibold">
        <Bell className="h-4 w-4 text-accent" /> KnowledgeOps AI
      </div>
      <div className="ml-auto flex items-center gap-2">
        <NotificationsBell />

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-ink-muted hover:bg-surface-700 hover:text-ink"
            >
              <span className="grid h-7 w-7 place-content-center rounded-full bg-surface-600 text-xs font-semibold text-ink">
                {initials}
              </span>
              <span className="hidden sm:inline max-w-[160px] truncate">
                {data?.user.email ?? '…'}
              </span>
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={6}
              className="z-50 min-w-56 rounded-md border border-ink-faint bg-surface-800 p-1 shadow-card"
            >
              <div className="px-3 py-2 text-xs text-ink-subtle">
                {data?.workspace.name}
              </div>
              <DropdownMenu.Separator className="my-1 h-px bg-ink-faint" />
              <DropdownItem href="/settings" icon={<User className="h-4 w-4" />} label="Profile" />
              <DropdownItem
                href="/settings"
                icon={<Settings className="h-4 w-4" />}
                label="Settings"
              />
              <DropdownMenu.Separator className="my-1 h-px bg-ink-faint" />
              <DropdownMenu.Item
                onSelect={(e) => {
                  e.preventDefault();
                  void onLogout();
                }}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-ink-muted outline-none hover:bg-surface-700 hover:text-ink data-[highlighted]:bg-surface-700 data-[highlighted]:text-ink"
              >
                <LogOut className="h-4 w-4" />
                <span>{signingOut ? 'Signing out…' : 'Sign out'}</span>
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  );
}

function DropdownItem({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  return (
    <DropdownMenu.Item asChild>
      <Link
        href={href}
        className="flex items-center gap-2 rounded px-2 py-1.5 text-sm text-ink-muted hover:bg-surface-700 hover:text-ink data-[highlighted]:bg-surface-700 data-[highlighted]:text-ink"
      >
        {icon}
        <span>{label}</span>
      </Link>
    </DropdownMenu.Item>
  );
}
