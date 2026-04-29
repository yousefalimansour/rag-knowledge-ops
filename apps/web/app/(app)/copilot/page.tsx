'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';
import { type ConfidenceBreakdown, type Source, streamQuery } from '@/lib/ai';

type Phase = 'idle' | 'streaming' | 'done' | 'error';

export default function CopilotPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<Source[]>([]);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [reasoning, setReasoning] = useState<string>('');
  const [breakdown, setBreakdown] = useState<ConfidenceBreakdown | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setAnswer('');
    setSources([]);
    setConfidence(null);
    setReasoning('');
    setBreakdown(null);
    setError(null);
    setPhase('streaming');

    try {
      await streamQuery(
        { question: question.trim() },
        (evt) => {
          switch (evt.event) {
            case 'token':
              setAnswer((a) => a + evt.data.delta);
              break;
            case 'sources':
              setSources(evt.data.sources);
              break;
            case 'confidence':
              setConfidence(evt.data.confidence);
              setReasoning(evt.data.reasoning);
              setBreakdown(evt.data.breakdown);
              break;
            case 'done':
              setPhase('done');
              break;
            case 'error':
              setError(evt.data.message);
              setPhase('error');
              break;
          }
        },
        ctrl.signal,
      );
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      setError((err as Error).message || 'stream failed');
      setPhase('error');
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Copilot</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Ask anything about your workspace. Every answer cites the chunks it came from.
        </p>
      </header>

      <form onSubmit={ask} className="rounded-xl border border-ink-faint bg-surface-700 p-4 shadow-card">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="What did the onboarding policy say about the first week?"
          className="w-full resize-none rounded-md bg-control-input px-3 py-2 text-sm outline-none focus:border focus:border-ink"
        />
        <div className="mt-3 flex items-center justify-between text-xs text-ink-subtle">
          <span>Streamed via SSE · cited sources verified post-hoc.</span>
          <button
            type="submit"
            disabled={phase === 'streaming' || !question.trim()}
            className="rounded-md bg-control px-3 py-1.5 text-sm font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
          >
            {phase === 'streaming' ? 'Streaming…' : 'Ask'}
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {(phase !== 'idle' || answer) && (
        <section className="rounded-xl border border-ink-faint bg-surface-700 p-5 shadow-card space-y-4">
          <div>
            <h2 className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Answer</h2>
            <div className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">
              {answer || (phase === 'streaming' ? 'Thinking…' : '')}
            </div>
          </div>

          {confidence !== null && (
            <div>
              <h2 className="text-xs font-medium uppercase tracking-wide text-ink-subtle">Confidence</h2>
              <div className="mt-2 flex items-center gap-2">
                <ConfidenceBar value={confidence} />
                <span className="text-xs text-ink-muted">{(confidence * 100).toFixed(0)}%</span>
              </div>
              {breakdown && (
                <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-ink-subtle">
                  <div>top: {breakdown.top_score.toFixed(2)}</div>
                  <div>gap: {breakdown.score_gap.toFixed(2)}</div>
                  <div>diversity: {breakdown.diversity.toFixed(2)}</div>
                  <div>evidence: {breakdown.evidence_count.toFixed(2)}</div>
                </div>
              )}
              {reasoning && <p className="mt-2 text-xs text-ink-subtle">{reasoning}</p>}
            </div>
          )}

          {sources.length > 0 && (
            <div>
              <h2 className="text-xs font-medium uppercase tracking-wide text-ink-subtle">
                Sources ({sources.length})
              </h2>
              <ul className="mt-2 space-y-2">
                {sources.map((s) => (
                  <li
                    key={s.chunk_id}
                    className="rounded-lg border border-ink-faint bg-surface-800 p-3 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <Link
                        href={`/documents/${s.document_id}`}
                        className="font-medium hover:text-accent"
                      >
                        {s.title}
                      </Link>
                      <span className="text-xs text-ink-subtle">score {s.score.toFixed(3)}</span>
                    </div>
                    {s.heading && <div className="text-xs text-ink-muted mt-0.5">{s.heading}</div>}
                    <p className="mt-2 text-ink-muted">{s.snippet}…</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone =
    value >= 0.7
      ? 'bg-emerald-400'
      : value >= 0.4
      ? 'bg-amber-400'
      : 'bg-red-400';
  return (
    <div className="h-2 w-32 rounded-full bg-surface-600 overflow-hidden">
      <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
    </div>
  );
}
