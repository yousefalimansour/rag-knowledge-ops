import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { documentsApi } from './documents';
import { insightsApi } from './insights';
import { notificationsApi } from './notifications';

/** Asserts that the lib helpers serialize their filter args into the right
 *  query string. The `api()` global is stubbed to capture the URL it was
 *  called with. We don't care about the response shape here. */
describe('list filter query strings', () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('document', { cookie: '' });
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function calledUrl(): string {
    return fetchMock.mock.calls[0][0] as string;
  }

  it('documentsApi.list serializes status + source_type + q', async () => {
    await documentsApi.list({ status: 'ready', source_type: 'pdf', q: 'pricing' });
    const url = calledUrl();
    expect(url).toContain('/api/docs?');
    expect(url).toContain('status=ready');
    expect(url).toContain('source_type=pdf');
    expect(url).toContain('q=pricing');
  });

  it('documentsApi.list omits the query string when no filters are set', async () => {
    await documentsApi.list();
    expect(calledUrl()).toMatch(/\/api\/docs(?:$|\?$)/);
  });

  it('insightsApi.list serializes type + severity + state', async () => {
    await insightsApi.list({ type: 'conflict', severity: 'high', state: 'active' });
    const url = calledUrl();
    expect(url).toContain('type=conflict');
    expect(url).toContain('severity=high');
    expect(url).toContain('state=active');
  });

  it('insightsApi.list drops empty filter values', async () => {
    await insightsApi.list({ type: '', severity: 'high', state: '' });
    const url = calledUrl();
    expect(url).toContain('severity=high');
    expect(url).not.toContain('type=');
    expect(url).not.toContain('state=');
  });

  it('notificationsApi.list passes unread + limit', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], next_cursor: null, unread_count: 0 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    await notificationsApi.list({ unread: true, limit: 25 });
    const url = calledUrl();
    expect(url).toContain('unread=true');
    expect(url).toContain('limit=25');
  });
});
