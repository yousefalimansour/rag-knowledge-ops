import { api } from './api';

export type Severity = 'low' | 'medium' | 'high';
export type InsightType = 'conflict' | 'repeated_decision' | 'stale_document';
export type InsightState = 'active' | 'dismissed' | 'read';

export type InsightEvidence = {
  chunk_id: string;
  document_id: string;
  title: string;
  snippet: string;
  heading: string | null;
  page: number | null;
};

export type Insight = {
  id: string;
  workspace_id: string;
  type: string;
  title: string;
  summary: string;
  severity: Severity;
  confidence: number | null;
  evidence: InsightEvidence[];
  state: InsightState;
  created_at: string;
  updated_at: string;
};

export type InsightRun = {
  id: string;
  workspace_id: string;
  scope: string;
  trigger: 'post_ingest' | 'coordinator' | 'nightly' | 'manual';
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  error: string | null;
  source_doc_ids: string[];
  insights_generated: number;
  insights_skipped: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export const insightsApi = {
  list: (filters?: { type?: string; severity?: string; state?: string }) => {
    const qs = new URLSearchParams();
    Object.entries(filters || {}).forEach(([k, v]) => v && qs.set(k, v));
    const suffix = qs.toString() ? `?${qs}` : '';
    return api<{ items: Insight[]; next_cursor: string | null }>(`/api/insights${suffix}`);
  },
  get: (id: string) => api<Insight>(`/api/insights/${id}`),
  patchState: (id: string, state: InsightState) =>
    api<Insight>(`/api/insights/${id}`, { method: 'PATCH', json: { state } }),
  runs: () => api<{ items: InsightRun[] }>('/api/insights/runs'),
  triggerRun: (body: { scope: 'all' | 'documents' | 'type'; document_ids?: string[]; type?: string }) =>
    api<{ run_id: string; status: string }>('/api/insights/run', { method: 'POST', json: body }),
};
