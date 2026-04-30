import type { ReactNode } from 'react';

const TOKEN_RE = /[A-Za-z0-9_]+/g;

/** Wraps every match of any term (≥3 chars, case-insensitive) in a <mark>. */
export function highlightMatches(text: string, query: string): ReactNode {
  const terms = Array.from(query.matchAll(TOKEN_RE))
    .map((m) => m[0].toLowerCase())
    .filter((t) => t.length >= 3);
  if (terms.length === 0) return text;

  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const re = new RegExp(`(${escaped.join('|')})`, 'gi');

  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const start = m.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    parts.push(
      <mark
        key={`m-${start}`}
        className="rounded bg-accent-soft px-0.5 text-ink"
      >
        {m[0]}
      </mark>,
    );
    last = start + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
