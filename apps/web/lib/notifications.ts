import { api } from './api';

export type Notification = {
  id: string;
  user_id: string;
  workspace_id: string;
  type: 'insight_created' | 'ingest_completed' | 'ingest_failed';
  title: string;
  body: string | null;
  severity: 'low' | 'medium' | 'high' | 'info' | null;
  link_kind: 'insight' | 'document' | null;
  link_id: string | null;
  read_at: string | null;
  created_at: string;
};

export type NotificationList = {
  items: Notification[];
  next_cursor: string | null;
  unread_count: number;
};

export const notificationsApi = {
  list: (params?: { unread?: boolean; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.unread !== undefined) qs.set('unread', String(params.unread));
    if (params?.limit) qs.set('limit', String(params.limit));
    const suffix = qs.toString() ? `?${qs}` : '';
    return api<NotificationList>(`/api/notifications${suffix}`);
  },
  markRead: (id: string) =>
    api<Notification>(`/api/notifications/${id}`, { method: 'PATCH' }),
  markAllRead: () =>
    api<void>('/api/notifications/mark-all-read', { method: 'POST' }),
};
