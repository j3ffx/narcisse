import { describe, expect, it } from 'vitest';
import { formatDuration, remainingSeconds } from './time';
import type { Run } from './types';

const run = (id: number, done: number, status: Run['status'] = 'running'): Run => ({
  id,
  scan_id: 1,
  module: 'demo.fake',
  input_kind: 'name',
  input_value: 'Jeanne Exemple',
  status,
  progress_done: done,
  progress_total: 12,
  results_count: done,
  attempts: 1,
  retry_at: null,
  error_code: null,
  error_params: null,
  retryable: false,
  started_at: '2026-01-01T00:00:00Z',
  finished_at: null,
  updated_at: '2026-01-01T00:00:00Z',
});

describe('remainingSeconds', () => {
  it('measures the pace from when the page first saw the run', () => {
    expect(remainingSeconds(run(1, 4), 10_000)).toBeNull();
    expect(remainingSeconds(run(1, 4), 11_000)).toBeNull();
    // 2 steps in 5 s: 6 steps left take 15 s, however long ago the run first started.
    expect(remainingSeconds(run(1, 6), 15_000)).toBe(15);
  });

  it('starts over when the run stops running', () => {
    remainingSeconds(run(2, 1), 0);
    expect(remainingSeconds(run(2, 3, 'paused'), 1_000)).toBeNull();
    expect(remainingSeconds(run(2, 3), 60_000)).toBeNull();
    expect(remainingSeconds(run(2, 4), 62_000)).toBe(16);
  });
});

describe('formatDuration', () => {
  it.each([
    [42, '42 s'],
    [150, '3 min'],
    [3900, '1 h 05'],
  ])('%s s reads « %s »', (seconds, text) => {
    expect(formatDuration(seconds)).toBe(text);
  });
});
