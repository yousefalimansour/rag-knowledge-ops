import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, ApiError } from './api';

describe('api()', () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('document', { cookie: 'csrf_token=abc123' });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it('attaches CSRF header on POST when csrf_token cookie present', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    await api('/auth/login', { method: 'POST', json: { email: 'a@b.c', password: 'x' } });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get('x-csrf-token')).toBe('abc123');
    expect(headers.get('content-type')).toBe('application/json');
    expect(init.credentials).toBe('include');
  });

  it('throws ApiError with detail on non-2xx', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid email or password' }), {
        status: 401,
        headers: { 'content-type': 'application/problem+json' },
      }),
    );
    const err = (await api('/auth/login', { method: 'POST', json: {} }).catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(err.detail).toBe('Invalid email or password');
  });
});
