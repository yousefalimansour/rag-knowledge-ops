import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { highlightMatches } from './highlight';

describe('highlightMatches', () => {
  it('wraps every term match in a <mark>, case-insensitive', () => {
    const node = highlightMatches('The pricing policy bumps the discount', 'pricing discount');
    const { container } = render(<>{node}</>);
    const marks = container.querySelectorAll('mark');
    expect(marks).toHaveLength(2);
    expect(marks[0].textContent).toBe('pricing');
    expect(marks[1].textContent).toBe('discount');
  });

  it('returns the original string when no terms match', () => {
    const node = highlightMatches('nothing to see here', 'xyz123');
    const { container } = render(<>{node}</>);
    expect(container.querySelectorAll('mark')).toHaveLength(0);
    expect(container.textContent).toBe('nothing to see here');
  });

  it('drops query terms shorter than 3 chars (avoids highlighting "a"/"is")', () => {
    const node = highlightMatches('a bigger answer', 'a bigger');
    const { container } = render(<>{node}</>);
    const marks = container.querySelectorAll('mark');
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe('bigger');
  });
});
