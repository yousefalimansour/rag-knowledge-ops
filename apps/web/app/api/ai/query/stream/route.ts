/**
 * SSE pipe-through to the FastAPI backend.
 *
 * Why this lives here instead of relying on `next.config.mjs` rewrites:
 * Next.js's dev rewrite proxy buffers/times-out long-lived streaming
 * responses, ECONNRESETing the upstream once Gemini takes >~30s. A native
 * Route Handler can hand the upstream `ReadableStream` straight back to
 * the browser without buffering, so 60s+ Gemini answers stream end-to-end.
 */
import { NextRequest } from 'next/server';

// Force the Node.js runtime — `fetch` in edge runtime would also stream,
// but the cookie + container-DNS story is simpler in Node.
export const runtime = 'nodejs';
// Don't pre-render or cache anything about this route.
export const dynamic = 'force-dynamic';

const UPSTREAM = process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';

export async function POST(req: NextRequest) {
  const body = await req.text();

  // Mirror cookies, content-type, and the CSRF header so the upstream
  // auth middleware sees the same request the browser sent.
  const headers = new Headers();
  headers.set('content-type', req.headers.get('content-type') ?? 'application/json');
  const cookie = req.headers.get('cookie');
  if (cookie) headers.set('cookie', cookie);
  const csrf = req.headers.get('x-csrf-token');
  if (csrf) headers.set('x-csrf-token', csrf);

  const upstream = await fetch(`${UPSTREAM}/api/ai/query/stream`, {
    method: 'POST',
    headers,
    body,
    // No `cache`, no signal: let the upstream drive the lifetime.
  });

  // Pipe upstream → TransformStream → response. Returning the raw
  // `upstream.body` lets Next.js's dev runtime buffer the response (it
  // can't tell the body is "ongoing"); copying chunk-by-chunk into a
  // TransformStream's writable side forces flush-as-you-go, so SSE
  // events show up in the browser the moment the api emits them.
  const { readable, writable } = new TransformStream<Uint8Array, Uint8Array>();
  if (upstream.body) {
    upstream.body
      .pipeTo(writable)
      .catch((err) => console.error('SSE pipe error', err));
  } else {
    writable.close().catch(() => {});
  }

  const responseHeaders = new Headers();
  responseHeaders.set(
    'content-type',
    upstream.headers.get('content-type') ?? 'text/event-stream',
  );
  responseHeaders.set('cache-control', 'no-cache, no-transform');
  responseHeaders.set('connection', 'keep-alive');
  responseHeaders.set('x-accel-buffering', 'no');

  return new Response(readable, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
