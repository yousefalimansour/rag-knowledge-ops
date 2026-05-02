import { api } from './api';

export type Source = {
  document_id: string;
  title: string;
  chunk_id: string;
  snippet: string;
  score: number;
  page: number | null;
  heading: string | null;
  source_type: string;
  chunk_index: number;
};

export type ConfidenceBreakdown = {
  top_score: number;
  score_gap: number;
  diversity: number;
  evidence_count: number;
};

export type QueryResult = {
  answer: string;
  sources: Source[];
  confidence: number;
  breakdown: ConfidenceBreakdown;
  reasoning: string;
  cached: boolean;
};

export type SearchResult = {
  chunk_id: string;
  document_id: string;
  title: string;
  snippet: string;
  source_type: string;
  heading: string | null;
  page: number | null;
  chunk_index: number;
  score: number;
  rerank_score: number | null;
  vector_rank: number | null;
  keyword_rank: number | null;
};

export type SearchEnvelope = {
  query: string;
  rewrites: string[];
  results: SearchResult[];
  debug: Record<string, unknown>;
};

export const aiApi = {
  query: (body: { question: string; top_k?: number; use_query_rewrite?: boolean }) =>
    api<QueryResult>('/api/ai/query', { method: 'POST', json: { ...body } }),
  search: (q: string, top_k = 10) =>
    api<SearchEnvelope>(`/api/search?q=${encodeURIComponent(q)}&top_k=${top_k}`),
};

export type StagePhase = 'retrieving' | 'reasoning';

export type StreamEvent =
  | { event: 'start'; data: { question: string } }
  | { event: 'stage'; data: { phase: StagePhase } }
  | { event: 'token'; data: { delta: string } }
  | { event: 'sources'; data: { sources: Source[] } }
  | { event: 'confidence'; data: { confidence: number; reasoning: string; breakdown: ConfidenceBreakdown } }
  | { event: 'done'; data: { ok: boolean } }
  | { event: 'error'; data: { message: string } };

/** Server-Sent Events client for /api/ai/query/stream.
 *
 * EventSource doesn't support POST, so we use fetch + a stream reader.
 */
export async function streamQuery(
  body: { question: string; top_k?: number; use_query_rewrite?: boolean },
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const csrf = readCookie('csrf_token');
  const res = await fetch('/api/ai/query/stream', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'content-type': 'application/json',
      ...(csrf ? { 'x-csrf-token': csrf } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`stream failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex: number;
    while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const evt = parseSseBlock(raw);
      if (evt) onEvent(evt);
    }
  }
}

function parseSseBlock(block: string): StreamEvent | null {
  let event = 'message';
  const dataLines: string[] = [];
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    const data = JSON.parse(dataLines.join('\n'));
    return { event, data } as StreamEvent;
  } catch {
    return null;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}
