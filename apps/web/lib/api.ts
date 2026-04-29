/**
 * Same-origin fetch wrapper. The Next.js rewrite in next.config.mjs forwards
 * /api/* and /auth/* to the FastAPI backend, so cookies are first-party.
 *
 * For state-changing requests, we read the (non-HttpOnly) `csrf_token` cookie
 * and echo it back in the `x-csrf-token` header — the FastAPI CSRFMiddleware
 * verifies the double-submit.
 */

export class ApiError extends Error {
  status: number;
  detail?: string;
  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

const SAFE = new Set(['GET', 'HEAD', 'OPTIONS']);

export async function api<T = unknown>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const method = (init.method || 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  let body = init.body;

  if (init.json !== undefined) {
    headers.set('content-type', 'application/json');
    body = JSON.stringify(init.json);
  }
  if (!SAFE.has(method)) {
    const csrf = readCookie('csrf_token');
    if (csrf) headers.set('x-csrf-token', csrf);
  }

  const res = await fetch(path, {
    ...init,
    method,
    headers,
    body,
    credentials: 'include',
  });

  const ct = res.headers.get('content-type') || '';
  const payload = ct.includes('json') ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    const detail =
      typeof payload === 'object' && payload && 'detail' in payload
        ? String((payload as { detail?: unknown }).detail)
        : typeof payload === 'string'
          ? payload
          : res.statusText;
    throw new ApiError(detail || res.statusText, res.status, detail);
  }
  return payload as T;
}
