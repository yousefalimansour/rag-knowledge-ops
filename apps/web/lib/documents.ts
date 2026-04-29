import { api } from './api';

export type Document = {
  id: string;
  workspace_id: string;
  title: string;
  source_type: 'pdf' | 'txt' | 'md' | 'slack' | 'notion';
  original_filename: string | null;
  content_hash: string;
  version: number;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  chunk_count: number;
  error: string | null;
  source_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
};

export type ChunkPreview = {
  id: string;
  chunk_index: number;
  text: string;
  heading: string | null;
  page_number: number | null;
};

export type DocumentList = { items: Document[]; next_cursor: string | null };
export type DocumentDetail = { document: Document; chunks_preview: ChunkPreview[] };

export type Job = {
  id: string;
  document_id: string;
  workspace_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  stage: string | null;
  error: string | null;
  attempts: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type IngestJobResult = {
  id: string;
  document_id: string;
  status: string;
  deduplicated: boolean;
};

export type SourcePayload = {
  source: 'slack' | 'notion';
  title: string;
  payload: Record<string, unknown>;
};

export const documentsApi = {
  list: (params?: { status?: string; source_type?: string; q?: string; cursor?: string }) => {
    const qs = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v) qs.set(k, v);
    });
    const suffix = qs.toString() ? `?${qs}` : '';
    return api<DocumentList>(`/api/docs${suffix}`);
  },
  get: (id: string) => api<DocumentDetail>(`/api/docs/${id}`),
};

export const ingestApi = {
  uploadFiles: async (files: File[]) => {
    const fd = new FormData();
    for (const f of files) fd.append('files', f, f.name);
    const csrf = readCookie('csrf_token');
    const res = await fetch('/api/ingest/files', {
      method: 'POST',
      credentials: 'include',
      headers: csrf ? { 'x-csrf-token': csrf } : undefined,
      body: fd,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const detail =
        (body && typeof body === 'object' && 'detail' in body && String((body as { detail: unknown }).detail)) ||
        res.statusText;
      throw new Error(detail);
    }
    return (await res.json()) as { jobs: IngestJobResult[] };
  },
  source: (body: SourcePayload) =>
    api<{ job: IngestJobResult }>('/api/ingest/source', { method: 'POST', json: body }),
};

export const jobsApi = {
  get: (id: string) => api<Job>(`/api/jobs/${id}`),
};

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}
