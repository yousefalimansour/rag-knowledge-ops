'use client';

import * as Tabs from '@radix-ui/react-tabs';
import { CheckCircle2, FileWarning, FilesIcon, Upload as UploadIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/toast';
import { ApiError } from '@/lib/api';
import { ingestApi } from '@/lib/documents';

const ACCEPT_EXT = ['.pdf', '.txt', '.md', '.markdown'];
const MAX_BYTES = 25 * 1024 * 1024;

type Row = {
  file: File;
  status: 'queued' | 'uploading' | 'done' | 'duplicate' | 'failed';
  message?: string;
};

export default function UploadPage() {
  const router = useRouter();
  const toast = useToast();
  const [rows, setRows] = useState<Row[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const arr = Array.from(files);
      const next: Row[] = [];
      for (const f of arr) {
        const ok = ACCEPT_EXT.some((e) => f.name.toLowerCase().endsWith(e));
        if (!ok) {
          next.push({ file: f, status: 'failed', message: 'Unsupported type' });
          continue;
        }
        if (f.size > MAX_BYTES) {
          next.push({ file: f, status: 'failed', message: 'Exceeds 25 MB' });
          continue;
        }
        next.push({ file: f, status: 'queued' });
      }
      setRows((cur) => [...cur, ...next]);
    },
    [],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    },
    [addFiles],
  );

  async function uploadAll() {
    const queued = rows.filter((r) => r.status === 'queued');
    if (queued.length === 0) return;

    setRows((cur) =>
      cur.map((r) => (r.status === 'queued' ? { ...r, status: 'uploading' } : r)),
    );

    try {
      const res = await ingestApi.uploadFiles(queued.map((r) => r.file));
      // Map results back by index — `ingestApi.uploadFiles` preserves order.
      setRows((cur) => {
        const newRows = [...cur];
        let ji = 0;
        for (let i = 0; i < newRows.length; i++) {
          if (newRows[i].status !== 'uploading') continue;
          const job = res.jobs[ji++];
          if (!job) continue;
          newRows[i] = {
            ...newRows[i],
            status: job.deduplicated ? 'duplicate' : 'done',
            message: job.deduplicated ? 'Already in workspace' : 'Queued for processing',
          };
        }
        return newRows;
      });

      const newCount = res.jobs.filter((j) => !j.deduplicated).length;
      const dupCount = res.jobs.length - newCount;
      toast.success(
        `${newCount} file${newCount === 1 ? '' : 's'} queued`,
        dupCount > 0 ? `${dupCount} already in workspace.` : undefined,
      );
      if (newCount > 0) {
        setTimeout(() => router.push('/documents'), 800);
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail || e.message : (e as Error).message;
      setRows((cur) =>
        cur.map((r) => (r.status === 'uploading' ? { ...r, status: 'failed', message: msg } : r)),
      );
      toast.error('Upload failed', msg);
    }
  }

  const queuedCount = rows.filter((r) => r.status === 'queued').length;

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Upload</h1>
        <p className="mt-1 text-sm text-ink-muted">PDF, TXT, or Markdown — or paste Slack / Notion JSON.</p>
      </header>

      <Tabs.Root defaultValue="files" className="space-y-4">
        <Tabs.List className="inline-flex rounded-md bg-surface-700 p-1 text-sm">
          <TabsTrigger value="files">Files</TabsTrigger>
          <TabsTrigger value="source">External source</TabsTrigger>
        </Tabs.List>

        <Tabs.Content value="files" className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={onDrop}
            className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
              dragActive
                ? 'border-accent bg-accent-soft/30'
                : 'border-ink-faint bg-surface-700/50 hover:bg-surface-700'
            }`}
          >
            <FilesIcon className="mx-auto h-7 w-7 text-ink-subtle" />
            <p className="mt-3 text-sm font-medium">Drop files here</p>
            <p className="text-xs text-ink-muted">or click to browse · max 25 MB each</p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-control px-3 py-1.5 text-xs font-medium text-ink shadow-button hover:bg-surface-600"
            >
              <UploadIcon className="h-3.5 w-3.5" /> Browse
            </button>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={ACCEPT_EXT.join(',')}
              aria-label="Upload files"
              className="hidden"
              onChange={(e) => {
                if (e.target.files) addFiles(e.target.files);
                e.target.value = '';
              }}
            />
          </div>

          {rows.length > 0 && (
            <div className="rounded-lg border border-ink-faint bg-surface-700 shadow-card overflow-hidden">
              <ul className="divide-y divide-ink-faint">
                {rows.map((r, i) => (
                  <li key={i} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                    <FileWarning className={`h-4 w-4 ${
                      r.status === 'failed' ? 'text-red-300' : 'text-ink-subtle'
                    }`} />
                    <span className="flex-1 truncate">{r.file.name}</span>
                    <span className="text-xs text-ink-subtle">{prettyBytes(r.file.size)}</span>
                    <RowStatus row={r} />
                  </li>
                ))}
              </ul>
              <div className="flex items-center justify-between gap-3 border-t border-ink-faint px-3 py-2">
                <span className="text-xs text-ink-subtle">
                  {queuedCount} ready · {rows.length - queuedCount} processed
                </span>
                <button
                  type="button"
                  disabled={queuedCount === 0}
                  onClick={() => void uploadAll()}
                  className="rounded-md bg-control px-3 py-1.5 text-xs font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
                >
                  Upload {queuedCount > 0 ? `(${queuedCount})` : ''}
                </button>
              </div>
            </div>
          )}
        </Tabs.Content>

        <Tabs.Content value="source">
          <SourcePasteForm />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function RowStatus({ row }: { row: Row }) {
  if (row.status === 'queued') return <Badge tone="muted">queued</Badge>;
  if (row.status === 'uploading') return <Badge tone="info">uploading…</Badge>;
  if (row.status === 'done')
    return (
      <Badge tone="success">
        <CheckCircle2 className="h-3 w-3" /> queued
      </Badge>
    );
  if (row.status === 'duplicate') return <Badge tone="muted">duplicate</Badge>;
  return <Badge tone="danger">{row.message ?? 'failed'}</Badge>;
}

function TabsTrigger({ value, children }: { value: string; children: React.ReactNode }) {
  return (
    <Tabs.Trigger
      value={value}
      className="rounded px-3 py-1.5 text-ink-muted data-[state=active]:bg-surface-600 data-[state=active]:text-ink hover:text-ink"
    >
      {children}
    </Tabs.Trigger>
  );
}

function SourcePasteForm() {
  const toast = useToast();
  const router = useRouter();
  const [source, setSource] = useState<'slack' | 'notion'>('slack');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    let payload: unknown;
    try {
      payload = JSON.parse(body);
    } catch {
      setErr('Body must be valid JSON.');
      return;
    }
    if (!title.trim()) {
      setErr('Title is required.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await ingestApi.source({ source, title: title.trim(), payload: payload as Record<string, unknown> });
      toast.success(
        res.job.deduplicated ? 'Already in workspace' : 'Queued for processing',
      );
      setTimeout(() => router.push('/documents'), 800);
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail || e.message : (e as Error).message;
      setErr(msg);
      toast.error('Ingest failed', msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-xl border border-ink-faint bg-surface-700 p-4 shadow-card">
      <div className="flex gap-2">
        {(['slack', 'notion'] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSource(s)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              source === s ? 'bg-control text-ink' : 'bg-surface-800 text-ink-muted hover:text-ink'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <label className="block">
        <span className="text-xs text-ink-subtle">Title</span>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={source === 'slack' ? '#general — pricing thread' : 'Engineering home'}
          className="mt-1 w-full rounded-md bg-control-input px-3 py-2 text-sm outline-none focus:border focus:border-ink"
        />
      </label>

      <label className="block">
        <span className="text-xs text-ink-subtle">JSON payload</span>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={10}
          spellCheck={false}
          placeholder={
            source === 'slack'
              ? '{\n  "channel": "general",\n  "messages": [\n    {"user":"alice","ts":"1717084800.000100","text":"hi"}\n  ]\n}'
              : '{\n  "title": "Engineering",\n  "blocks": [\n    {"type":"heading_1","text":"Onboarding"},\n    {"type":"paragraph","text":"..."}\n  ]\n}'
          }
          className="mt-1 w-full rounded-md bg-control-input px-3 py-2 text-xs font-mono outline-none focus:border focus:border-ink"
        />
      </label>

      {err && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {err}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-control px-3 py-1.5 text-xs font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
      >
        {submitting ? 'Sending…' : 'Ingest'}
      </button>
    </form>
  );
}

function prettyBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
