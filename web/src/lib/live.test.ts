import { describe, expect, it } from 'vitest';
import {
  cancelled,
  inActivity,
  matches,
  paused,
  resumed,
  retried,
  withProgress,
  withResult,
  withRun,
  withScan,
} from './live';
import type { Result, Run, ScanDetail } from './types';

const run = (id: number, status: Run['status'] = 'running'): Run => ({
  id,
  scan_id: 1,
  module: 'demo.fake',
  input_kind: 'name',
  input_value: 'Jeanne Exemple',
  status,
  progress_done: 0,
  progress_total: 12,
  results_count: 0,
  attempts: 1,
  retry_at: null,
  error_code: null,
  error_params: null,
  retryable: false,
  started_at: null,
  finished_at: null,
  updated_at: '2026-01-01T00:00:00Z',
});

const scan = (...runs: Run[]): ScanDetail => ({
  id: 1,
  profile_id: 1,
  profile_name: 'Jeanne Exemple',
  status: 'running',
  modules: ['demo.fake'],
  results_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  finished_at: null,
  runs,
});

const result = (id: number, runId = 1, display = 'https://forum.example.org/u/jeanne'): Result => ({
  id,
  scan_id: 1,
  run_id: runId,
  module: 'demo.fake',
  entity: {
    id,
    kind: 'account',
    display,
    normalized: display,
    status: 'unreviewed',
    confidence: 0.5,
  },
  relation: 'has_account',
  confidence: 0.5,
  url: display,
  excerpt: null,
  captured_at: '2026-01-01T00:00:00Z',
});

describe('live events', () => {
  it('replace a run, or add one the page did not know', () => {
    const updated = withRun(scan(run(1), run(2)), { ...run(2), status: 'done' });
    expect(updated.runs.map((r) => r.status)).toEqual(['running', 'done']);
    expect(withRun(scan(run(1)), run(3)).runs).toHaveLength(2);
    expect(withRun(scan(run(1)), { ...run(4), scan_id: 9 }).runs).toHaveLength(1);
  });

  it('update a scan without losing its runs', () => {
    const detail = scan(run(1));
    const updated = withScan(detail, { ...detail, status: 'done' });
    expect(updated.status).toBe('done');
    expect(updated.runs).toHaveLength(1);
  });

  it('count a result on the scan and its run', () => {
    const updated = withResult(scan(run(1), run(2)), result(10, 2));
    expect(updated.results_count).toBe(1);
    expect(updated.runs.map((r) => r.results_count)).toEqual([0, 1]);
  });

  it('move a progress bar', () => {
    const updated = withProgress(scan(run(1)), { run_id: 1, scan_id: 1, done: 5, total: 12 });
    expect(updated.runs[0]?.progress_done).toBe(5);
  });

  it('add a new scan to the activity centre, first', () => {
    const activity = { last_event_id: 0, scans: [{ ...scan(), id: 2 }] };
    const added = inActivity(activity, 1, (s) => s, scan());
    expect(added.scans.map((s) => s.id)).toEqual([1, 2]);
    expect(inActivity(activity, 3, (s) => s)).toBe(activity);
  });
});

describe('optimistic commands', () => {
  const detail = scan(run(1), run(2, 'done'), run(3, 'rate_limited'));

  it('pause what is not finished', () => {
    expect(paused(detail).runs.map((r) => r.status)).toEqual(['paused', 'done', 'paused']);
  });

  it('resume paused runs into the queue', () => {
    expect(resumed(paused(detail)).runs.map((r) => r.status)).toEqual(['queued', 'done', 'queued']);
  });

  it('cancel what is not finished', () => {
    expect(cancelled(detail).runs.map((r) => r.status)).toEqual(['cancelled', 'done', 'cancelled']);
  });

  it('reopen a finished scan when a run is retried', () => {
    const done = {
      ...scan({ ...run(1, 'failed'), error_code: 'source_unavailable' }),
      status: 'done' as const,
    };
    const updated = retried(done, 1);
    expect(updated.status).toBe('running');
    expect(updated.runs[0]).toMatchObject({ status: 'queued', error_code: null });
  });
});

describe('matches', () => {
  it('filters by kind and by text in the value or the address', () => {
    const r = result(1);
    expect(matches(r, null, '')).toBe(true);
    expect(matches(r, 'account', 'FORUM')).toBe(true);
    expect(matches(r, 'email', '')).toBe(false);
    expect(matches(r, null, 'photos')).toBe(false);
  });
});
