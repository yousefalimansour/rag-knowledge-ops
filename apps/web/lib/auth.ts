import { api } from './api';

export type User = { id: string; email: string; created_at: string };
export type Workspace = { id: string; name: string; created_at: string };
export type AuthEnvelope = { user: User; workspace: Workspace };

export const authApi = {
  signup: (email: string, password: string) =>
    api<AuthEnvelope>('/auth/signup', { method: 'POST', json: { email, password } }),
  login: (email: string, password: string) =>
    api<AuthEnvelope>('/auth/login', { method: 'POST', json: { email, password } }),
  logout: () => api<void>('/auth/logout', { method: 'POST' }),
  me: () => api<AuthEnvelope>('/auth/me'),
};
