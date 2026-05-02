'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { AlertTriangle, MessageSquare, Send, Sparkles } from 'lucide-react';
import { type ConfidenceBreakdown, type Source, type StagePhase, streamQuery } from '@/lib/ai';
import { AnswerRenderer } from '@/components/app/answer-renderer';
import { SourcePreviewSheet } from '@/components/app/source-preview-sheet';
import { ThinkingCandles } from '@/components/app/thinking-candles';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/toast';

const REFUSAL_TEXT = "I don't have evidence about this in the knowledge base.";

type Phase = 'idle' | 'streaming' | 'done' | 'error';

type Turn = {
  id: number;
  question: string;
  answer: string;
  sources: Source[];
  confidence: number | null;
  reasoning: string;
  breakdown: ConfidenceBreakdown | null;
  phase: Phase;
  stage: StagePhase | null;
  error: string | null;
};

let nextId = 0;

export function CopilotClient() {
  const params = useSearchParams();
  const initialQuestion = params.get('q') ?? '';
  const toast = useToast();

  const [draft, setDraft] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [previewSource, setPreviewSource] = useState<Source | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const seededRef = useRef(false);

  // Auto-scroll on new content
  useEffect(() => {
    scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: 'smooth' });
  }, [turns]);

  // Seed from `?q=…` once
  useEffect(() => {
    if (seededRef.current || !initialQuestion) return;
    seededRef.current = true;
    void ask(initialQuestion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  async function ask(question: string) {
    const text = question.trim();
    if (!text) return;
    setDraft('');

    const id = ++nextId;
    setTurns((cur) => [
      ...cur,
      {
        id,
        question: text,
        answer: '',
        sources: [],
        confidence: null,
        reasoning: '',
        breakdown: null,
        phase: 'streaming',
        stage: null,
        error: null,
      },
    ]);

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const update = (patch: Partial<Turn>) =>
      setTurns((cur) => cur.map((t) => (t.id === id ? { ...t, ...patch } : t)));

    try {
      await streamQuery({ question: text }, (evt) => {
        switch (evt.event) {
          case 'stage':
            update({ stage: evt.data.phase });
            break;
          case 'token':
            setTurns((cur) =>
              cur.map((t) => (t.id === id ? { ...t, answer: t.answer + evt.data.delta } : t)),
            );
            break;
          case 'sources':
            update({ sources: evt.data.sources });
            break;
          case 'confidence':
            update({
              confidence: evt.data.confidence,
              reasoning: evt.data.reasoning,
              breakdown: evt.data.breakdown,
            });
            break;
          case 'done':
            update({ phase: 'done' });
            break;
          case 'error':
            update({ phase: 'error', error: evt.data.message });
            toast.error('Copilot error', evt.data.message);
            break;
        }
      }, ctrl.signal);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      const msg = (err as Error).message || 'stream failed';
      update({ phase: 'error', error: msg });
      toast.error('Copilot error', msg);
    }
  }

  const lastTurn = turns.at(-1);
  const isStreaming = lastTurn?.phase === 'streaming';

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-4xl flex-col">
      <header className="mb-3">
        <h1 className="text-2xl font-semibold tracking-tight">Copilot</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Streamed answers grounded in your workspace. Click any citation to inspect the source chunk.
        </p>
      </header>

      <div
        ref={scrollerRef}
        className="flex-1 overflow-y-auto rounded-xl border border-ink-faint bg-surface-700/50 p-4 space-y-6"
      >
        {turns.length === 0 && <WelcomeState onPick={(q) => ask(q)} />}
        {turns.map((t) => (
          <TurnView key={t.id} turn={t} onCitationClick={setPreviewSource} />
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(draft);
        }}
        className="mt-3 flex gap-2"
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={1}
          placeholder="Ask anything…"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void ask(draft);
            }
          }}
          className="flex-1 resize-none rounded-md bg-control-input px-3 py-2 text-sm outline-none focus:border focus:border-ink"
        />
        <button
          type="submit"
          disabled={isStreaming || !draft.trim()}
          className="inline-flex items-center gap-1.5 rounded-md bg-control px-3 py-2 text-sm font-medium text-ink shadow-button hover:bg-surface-600 disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
          {isStreaming ? 'Streaming…' : 'Send'}
        </button>
      </form>

      <SourcePreviewSheet source={previewSource} onOpenChange={(o) => !o && setPreviewSource(null)} />
    </div>
  );
}

function stageLabel(stage: StagePhase | null): string {
  switch (stage) {
    case 'retrieving':
      return 'Searching your knowledge base…';
    case 'reasoning':
      return 'Reasoning over sources…';
    default:
      return 'Thinking…';
  }
}

function TurnView({
  turn,
  onCitationClick,
}: {
  turn: Turn;
  onCitationClick: (s: Source) => void;
}) {
  const isRefusal = turn.answer.trim() === REFUSAL_TEXT;

  return (
    <article className="space-y-3">
      <div className="flex items-start gap-2">
        <div className="mt-0.5 grid h-6 w-6 place-content-center rounded-full bg-surface-600 text-[10px] font-semibold">
          You
        </div>
        <div className="flex-1 rounded-md bg-surface-800 px-3 py-2 text-sm whitespace-pre-wrap">
          {turn.question}
        </div>
      </div>

      <div className="flex items-start gap-2">
        <div className="mt-0.5 grid h-6 w-6 place-content-center rounded-full bg-accent-soft text-accent">
          <MessageSquare className="h-3.5 w-3.5" />
        </div>
        <div
          className={`flex-1 rounded-md px-3 py-2.5 text-sm border ${
            isRefusal
              ? 'border-amber-500/40 bg-amber-500/5'
              : 'border-ink-faint bg-surface-800'
          }`}
        >
          {isRefusal && (
            <div className="mb-2 inline-flex items-center gap-1.5">
              <Badge tone="warning">
                <AlertTriangle className="h-3 w-3" />
                Not enough evidence
              </Badge>
            </div>
          )}

          {turn.answer ? (
            isRefusal ? (
              <p className="text-ink-muted">{turn.answer}</p>
            ) : (
              <AnswerRenderer text={turn.answer} sources={turn.sources} onCitationClick={onCitationClick} />
            )
          ) : turn.phase === 'streaming' ? (
            <ThinkingCandles label={stageLabel(turn.stage)} />
          ) : null}

          {turn.error && (
            <p className="mt-2 text-xs text-red-300">{turn.error}</p>
          )}

          {turn.confidence !== null && (
            <ConfidenceFooter
              confidence={turn.confidence}
              breakdown={turn.breakdown}
              reasoning={turn.reasoning}
              sourcesCount={turn.sources.length}
            />
          )}

          {turn.sources.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {turn.sources.map((s, i) => (
                <li key={s.chunk_id}>
                  <button
                    type="button"
                    onClick={() => onCitationClick(s)}
                    className="inline-flex max-w-[280px] items-center gap-1 truncate rounded-md border border-ink-faint bg-surface-700 px-2 py-1 text-xs text-ink-muted hover:bg-surface-600 hover:text-ink"
                    title={s.snippet}
                  >
                    <span className="grid h-4 w-4 shrink-0 place-content-center rounded bg-accent-soft text-[9px] font-semibold text-accent">
                      {i + 1}
                    </span>
                    <span className="truncate">{s.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </article>
  );
}

function ConfidenceFooter({
  confidence,
  breakdown,
  reasoning,
  sourcesCount,
}: {
  confidence: number;
  breakdown: ConfidenceBreakdown | null;
  reasoning: string;
  sourcesCount: number;
}) {
  const pct = Math.max(0, Math.min(1, confidence)) * 100;
  const tone = confidence >= 0.7 ? 'bg-emerald-400' : confidence >= 0.4 ? 'bg-amber-400' : 'bg-red-400';
  return (
    <div className="mt-3 border-t border-ink-faint pt-2 text-xs text-ink-subtle">
      <div className="flex items-center gap-2">
        <span>confidence</span>
        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-600">
          <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
        </div>
        <span>{(confidence * 100).toFixed(0)}%</span>
        <span className="text-ink-muted">·</span>
        <span>{sourcesCount} source{sourcesCount === 1 ? '' : 's'}</span>
      </div>
      {breakdown && (
        <div className="mt-1 flex gap-3 text-[11px]">
          <span>top {breakdown.top_score.toFixed(2)}</span>
          <span>gap {breakdown.score_gap.toFixed(2)}</span>
          <span>diversity {breakdown.diversity.toFixed(2)}</span>
          <span>evidence {breakdown.evidence_count.toFixed(2)}</span>
        </div>
      )}
      {reasoning && <p className="mt-1 text-[11px] leading-relaxed">{reasoning}</p>}
    </div>
  );
}

function WelcomeState({ onPick }: { onPick: (q: string) => void }) {
  const examples = [
    'Summarize the policies my team has documented.',
    'How much vacation accrues per month?',
    'When do I need manager approval for an expense?',
  ];
  return (
    <div className="mx-auto max-w-md py-6 text-center">
      <Sparkles className="mx-auto h-6 w-6 text-accent" />
      <h2 className="mt-3 text-base font-semibold">Ask anything in your workspace</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Answers stream in token-by-token. Every claim is cited and clickable.
      </p>
      <div className="mt-4 grid gap-2">
        {examples.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="rounded-md border border-ink-faint bg-surface-800 px-3 py-2 text-left text-sm text-ink-muted hover:bg-surface-700 hover:text-ink"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
