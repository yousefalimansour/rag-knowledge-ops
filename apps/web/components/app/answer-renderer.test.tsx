import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AnswerRenderer } from './answer-renderer';
import type { Source } from '@/lib/ai';

const ID_A = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const ID_B = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

const sourceA: Source = {
  document_id: 'd1',
  title: 'Pricing Policy v2',
  chunk_id: ID_A,
  snippet: 'Maximum enterprise discount is 25%.',
  score: 0.9,
  page: null,
  heading: null,
  source_type: 'md',
  chunk_index: 0,
};
const sourceB: Source = {
  ...sourceA,
  chunk_id: ID_B,
  title: 'Security Handbook',
  snippet: 'Argon2id for passwords.',
};

describe('AnswerRenderer', () => {
  it('renders numbered citation chips for known [uuid] markers', () => {
    render(
      <AnswerRenderer
        text={`Discount cap is 25% [${ID_A}]. Passwords use Argon2id [${ID_B}].`}
        sources={[sourceA, sourceB]}
        onCitationClick={() => {}}
      />,
    );
    // Two chips, numbered in order of first appearance.
    const chip1 = screen.getByRole('button', { name: /Open source 1: Pricing Policy v2/ });
    const chip2 = screen.getByRole('button', { name: /Open source 2: Security Handbook/ });
    expect(chip1.textContent).toBe('1');
    expect(chip2.textContent).toBe('2');
  });

  it('drops citations whose chunk_id is not in the sources list', () => {
    const ghost = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
    render(
      <AnswerRenderer
        text={`Cited [${ID_A}] and ghost [${ghost}].`}
        sources={[sourceA]}
        onCitationClick={() => {}}
      />,
    );
    expect(screen.getAllByRole('button')).toHaveLength(1);
    // Ghost id should be silently stripped, not rendered as text.
    expect(screen.queryByText(new RegExp(ghost))).toBeNull();
  });

  it('invokes onCitationClick with the matching source', () => {
    const onClick = vi.fn();
    render(
      <AnswerRenderer
        text={`See [${ID_A}].`}
        sources={[sourceA]}
        onCitationClick={onClick}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Open source 1/ }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledWith(sourceA);
  });
});
