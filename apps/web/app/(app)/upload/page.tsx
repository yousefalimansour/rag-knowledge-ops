'use client';

import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';
import { ingestApi } from '@/lib/documents';

const ACCEPT = '.pdf,.txt,.md,.markdown';

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    const files = Array.from(inputRef.current?.files ?? []);
    if (files.length === 0) {
      setError('Pick at least one file.');
      return;
    }

    setPending(true);
    try {
      const res = await ingestApi.uploadFiles(files);
      const dedup = res.jobs.filter((j) => j.deduplicated).length;
      const fresh = res.jobs.length - dedup;
      setResult(
        `${fresh} queued for processing` +
          (dedup > 0 ? `, ${dedup} already in workspace (deduplicated).` : '.'),
      );
      // Give the user a beat to read the result, then jump to the list.
      setTimeout(() => router.push('/documents'), 800);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Upload</h1>
        <p className="mt-1 text-sm text-ink-muted">PDF, TXT, or Markdown. Max 25 MB per file.</p>
      </header>

      <form
        onSubmit={onSubmit}
        className="rounded-xl border border-ink-faint bg-surface-700 p-6 shadow-card space-y-4"
      >
        <label className="block">
          <span className="text-sm font-medium">Files</span>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            className="mt-2 block w-full text-sm text-ink file:mr-3 file:rounded-md file:border-0 file:bg-control file:px-3 file:py-2 file:text-sm file:text-ink hover:file:bg-surface-600"
          />
        </label>

        {error && (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}
        {result && (
          <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
            {result}
          </div>
        )}

        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-control px-4 py-2 text-sm font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
        >
          {pending ? 'Uploading…' : 'Upload'}
        </button>
      </form>
    </div>
  );
}
