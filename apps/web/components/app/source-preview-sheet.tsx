'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { documentsApi, type Document } from '@/lib/documents';
import type { Source } from '@/lib/ai';
import { Sheet } from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';

type Props = {
  source: Source | null;
  onOpenChange: (open: boolean) => void;
};

export function SourcePreviewSheet({ source, onOpenChange }: Props) {
  const open = source !== null;
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', source?.document_id],
    queryFn: () => documentsApi.get(source!.document_id),
    enabled: open,
  });

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={source?.title ?? 'Source'}
      description={source ? metaLine(source) : undefined}
      widthClassName="w-full sm:max-w-lg"
    >
      {!source ? null : (
        <div className="space-y-5">
          <article className="rounded-lg border border-accent/40 bg-accent-soft/30 p-4 text-sm leading-relaxed">
            <Header label="Cited chunk" tone="info" />
            <p className="mt-2 whitespace-pre-wrap">{source.snippet}</p>
            <p className="mt-2 text-[11px] text-ink-subtle">
              chunk #{source.chunk_index} · score {source.score.toFixed(3)}
            </p>
          </article>

          <section>
            <Header label="Surrounding chunks" />
            <div className="mt-2 space-y-2">
              {isLoading && <Skeleton className="h-24 w-full" />}
              {error && <p className="text-xs text-red-300">Could not load context.</p>}
              {data && <ContextChunks data={data} pivotChunkId={source.chunk_id} />}
            </div>
          </section>

          {data && (
            <Link
              href={`/documents/${data.document.id}`}
              className="inline-flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink"
            >
              Open full document <ExternalLink className="h-3 w-3" />
            </Link>
          )}
        </div>
      )}
    </Sheet>
  );
}

function metaLine(s: Source): string {
  const bits = [s.source_type, s.heading, s.page != null ? `p.${s.page}` : null].filter(Boolean);
  return bits.join(' · ');
}

function Header({ label, tone }: { label: string; tone?: 'info' }) {
  return (
    <div className="flex items-center gap-2">
      {tone === 'info' && <Badge tone="info">cited</Badge>}
      <h3 className="text-xs font-medium uppercase tracking-wide text-ink-subtle">{label}</h3>
    </div>
  );
}

function ContextChunks({
  data,
  pivotChunkId,
}: {
  data: { document: Document; chunks_preview: { id: string; chunk_index: number; text: string; heading: string | null; page_number: number | null }[] };
  pivotChunkId: string;
}) {
  // The detail endpoint returns the first 5 chunks. Highlight the cited one
  // if it's in the preview window; otherwise show a hint and link to the doc.
  const chunks = data.chunks_preview;
  const pivotInWindow = chunks.some((c) => c.id === pivotChunkId);

  return (
    <>
      {chunks.map((c) => {
        const isPivot = c.id === pivotChunkId;
        return (
          <div
            key={c.id}
            className={`rounded-md border p-3 text-xs ${
              isPivot
                ? 'border-accent/60 bg-accent-soft/40 text-ink'
                : 'border-ink-faint bg-surface-800 text-ink-muted'
            }`}
          >
            <div className="text-[10px] uppercase tracking-wide text-ink-subtle">
              chunk #{c.chunk_index}
              {c.heading && ` · ${c.heading}`}
              {c.page_number != null && ` · p.${c.page_number}`}
            </div>
            <p className="mt-1.5 whitespace-pre-wrap">{c.text}</p>
          </div>
        );
      })}
      {!pivotInWindow && (
        <p className="text-[11px] text-ink-subtle">
          The cited chunk lives further into the document — open the full document to see it in
          context.
        </p>
      )}
    </>
  );
}
