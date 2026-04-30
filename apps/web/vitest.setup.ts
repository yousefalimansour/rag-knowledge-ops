import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Vitest 2 doesn't auto-call testing-library's `cleanup` between tests, so
// rendered nodes from one test would leak into the next.
afterEach(() => {
  cleanup();
});
