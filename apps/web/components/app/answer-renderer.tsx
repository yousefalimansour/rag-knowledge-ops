'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ReactNode } from 'react';
import type { Source } from '@/lib/ai';

const UUID_RE =
  /\[([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]/g;

type Props = {
  text: string;
  sources: Source[];
  onCitationClick: (source: Source) => void;
};

/** Renders the streamed answer as Markdown, with `[uuid]` citations replaced by
 *  numbered chips that open the source preview when clicked. */
export function AnswerRenderer({ text, sources, onCitationClick }: Props) {
  const sourceById = new Map(sources.map((s) => [s.chunk_id.toLowerCase(), s]));
  const ordered: string[] = [];
  for (const m of text.matchAll(UUID_RE)) {
    const id = m[1].toLowerCase();
    if (!ordered.includes(id) && sourceById.has(id)) ordered.push(id);
  }
  const numberById = new Map(ordered.map((id, i) => [id, i + 1]));

  // Replace each citation with a placeholder using Unicode Private Use Area
  // sentinels ( / ) so ReactMarkdown won't interpret the markers
  // as bold/italic — `__CITE__id__` was being parsed as a bold span.
  const PLACEHOLDER = (id: string) => `${id}`;
  const transformed = text.replace(UUID_RE, (_full, id: string) =>
    sourceById.has(id.toLowerCase()) ? PLACEHOLDER(id.toLowerCase()) : '',
  );

  return (
    <div className="text-sm leading-relaxed space-y-3">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="mb-3 last:mb-0">
              {splitChildren(children, sourceById, numberById, onCitationClick)}
            </p>
          ),
          ul: ({ children }) => <ul className="list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1">{children}</ol>,
          // eslint-disable-next-line jsx-a11y/no-redundant-roles
          li: ({ children }) => (
            // ReactMarkdown wraps these in ul/ol; the lint rule misfires.
            // eslint-disable-next-line @next/next/no-html-link-for-pages
            <li>{splitChildren(children, sourceById, numberById, onCitationClick)}</li>
          ),
          h1: ({ children }) => <h3 className="font-semibold text-base mt-1">{children}</h3>,
          h2: ({ children }) => <h3 className="font-semibold text-sm mt-1">{children}</h3>,
          h3: ({ children }) => <h4 className="font-semibold text-sm">{children}</h4>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent underline">
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-surface-900 px-1 py-0.5 text-[0.85em] text-accent">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="rounded-md bg-surface-900 p-3 text-xs overflow-x-auto">{children}</pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-ink-faint pl-3 text-ink-muted">{children}</blockquote>
          ),
        }}
      >
        {transformed}
      </ReactMarkdown>
    </div>
  );
}

function splitChildren(
  children: ReactNode,
  sourceById: Map<string, Source>,
  numberById: Map<string, number>,
  onClick: (s: Source) => void,
): ReactNode {
  const out: ReactNode[] = [];
  childArray(children).forEach((node, i) => {
    if (typeof node !== 'string') {
      out.push(<span key={`n-${i}`}>{node}</span>);
      return;
    }
    let cursor = 0;
    // Matches the Private Use Area sentinels we wrote into `transformed`.
    const markerRe = /([0-9a-fA-F-]+)/g;
    for (const match of node.matchAll(markerRe)) {
      const idx = match.index ?? 0;
      if (idx > cursor) out.push(node.slice(cursor, idx));
      const id = match[1].toLowerCase();
      const source = sourceById.get(id);
      const num = numberById.get(id);
      if (source && num != null) {
        out.push(
          <button
            key={`${id}-${idx}`}
            type="button"
            onClick={() => onClick(source)}
            className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-accent-soft px-1 text-[10px] font-semibold text-accent ring-1 ring-accent/40 hover:bg-accent/20"
            title={source.title}
            aria-label={`Open source ${num}: ${source.title}`}
          >
            {num}
          </button>,
        );
      }
      cursor = idx + match[0].length;
    }
    if (cursor < node.length) out.push(node.slice(cursor));
  });
  return out;
}

function childArray(children: ReactNode): ReactNode[] {
  if (Array.isArray(children)) return children;
  return [children];
}
