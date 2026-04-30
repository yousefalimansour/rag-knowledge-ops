'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, Check, CheckCheck } from 'lucide-react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { notificationsApi, type Notification } from '@/lib/notifications';

export function NotificationsBell() {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list({ limit: 10 }),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  });

  const unread = list.data?.unread_count ?? 0;
  const items = list.data?.items ?? [];

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Notifications"
          className="relative grid h-9 w-9 place-content-center rounded-md text-ink-muted hover:bg-surface-700 hover:text-ink"
        >
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 grid h-4 min-w-4 place-content-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
              {unread > 99 ? '99+' : unread}
            </span>
          )}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-50 w-80 max-h-[26rem] overflow-y-auto rounded-md border border-ink-faint bg-surface-800 p-1 shadow-card"
        >
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs font-medium uppercase tracking-wide text-ink-subtle">
              Notifications
            </span>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markAll.mutate()}
                disabled={markAll.isPending}
                className="inline-flex items-center gap-1 text-xs text-ink-muted hover:text-ink"
              >
                <CheckCheck className="h-3 w-3" />
                Mark all read
              </button>
            )}
          </div>
          <DropdownMenu.Separator className="my-1 h-px bg-ink-faint" />
          {items.length === 0 && (
            <p className="px-3 py-6 text-center text-xs text-ink-muted">No notifications yet.</p>
          )}
          {items.map((n) => (
            <NotificationRow
              key={n.id}
              notification={n}
              onClick={() => markRead.mutate(n.id)}
            />
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function NotificationRow({
  notification: n,
  onClick,
}: {
  notification: Notification;
  onClick: () => void;
}) {
  const href =
    n.link_kind === 'insight'
      ? '/insights'
      : n.link_kind === 'document' && n.link_id
        ? `/documents/${n.link_id}`
        : '#';
  const tone =
    n.severity === 'high'
      ? 'danger'
      : n.severity === 'medium'
        ? 'warning'
        : n.severity === 'info'
          ? 'info'
          : 'muted';
  const isUnread = n.read_at == null;

  return (
    <DropdownMenu.Item asChild>
      <Link
        href={href}
        onClick={onClick}
        className={`flex flex-col gap-1 rounded px-3 py-2 text-sm outline-none data-[highlighted]:bg-surface-700 ${
          isUnread ? 'bg-surface-700/40' : ''
        }`}
      >
        <div className="flex items-start gap-2">
          {n.severity && <Badge tone={tone}>{n.severity}</Badge>}
          <span className="flex-1 truncate font-medium">{n.title}</span>
          {isUnread && <Check className="h-3 w-3 text-accent" />}
        </div>
        {n.body && <p className="line-clamp-2 text-xs text-ink-muted">{n.body}</p>}
        <span className="text-[10px] text-ink-subtle">
          {new Date(n.created_at).toLocaleString()}
        </span>
      </Link>
    </DropdownMenu.Item>
  );
}
