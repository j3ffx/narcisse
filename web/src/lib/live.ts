// How live events and commands change what the UI holds. Pure functions, tested in live.test.ts.
import { FINISHED_RUN } from './labels';
import type { Activity, Result, Run, RunProgress, Scan, ScanDetail } from './types';

export function withScan(detail: ScanDetail, scan: Scan): ScanDetail {
  return { ...detail, ...scan, runs: detail.runs };
}

export function withRun(detail: ScanDetail, run: Run): ScanDetail {
  if (run.scan_id !== detail.id) return detail;
  const index = detail.runs.findIndex((r) => r.id === run.id);
  const runs =
    index === -1 ? [...detail.runs, run] : detail.runs.map((r, i) => (i === index ? run : r));
  return { ...detail, runs };
}

export function withProgress(detail: ScanDetail, progress: RunProgress): ScanDetail {
  if (progress.scan_id !== detail.id) return detail;
  return {
    ...detail,
    runs: detail.runs.map((r) =>
      r.id === progress.run_id
        ? { ...r, progress_done: progress.done, progress_total: progress.total }
        : r,
    ),
  };
}

export function withResult(detail: ScanDetail, result: Result): ScanDetail {
  if (result.scan_id !== detail.id) return detail;
  return {
    ...detail,
    results_count: detail.results_count + 1,
    runs: detail.runs.map((r) =>
      r.id === result.run_id ? { ...r, results_count: r.results_count + 1 } : r,
    ),
  };
}

/** Applies a change to one scan of the activity centre, or adds it when it is new. */
export function inActivity(
  activity: Activity,
  scanId: number,
  change: (scan: ScanDetail) => ScanDetail,
  created?: ScanDetail,
): Activity {
  if (!activity.scans.some((s) => s.id === scanId)) {
    return created ? { ...activity, scans: [created, ...activity.scans] } : activity;
  }
  return { ...activity, scans: activity.scans.map((s) => (s.id === scanId ? change(s) : s)) };
}

// What a command changes at once, before the server confirms it (optimistic updates).

export function paused(detail: ScanDetail): ScanDetail {
  return {
    ...detail,
    status: 'paused',
    runs: detail.runs.map((r) => (FINISHED_RUN.has(r.status) ? r : { ...r, status: 'paused' })),
  };
}

export function resumed(detail: ScanDetail): ScanDetail {
  return {
    ...detail,
    status: 'running',
    runs: detail.runs.map((r) => (r.status === 'paused' ? { ...r, status: 'queued' } : r)),
  };
}

export function cancelled(detail: ScanDetail): ScanDetail {
  return {
    ...detail,
    status: 'cancelled',
    runs: detail.runs.map((r) => (FINISHED_RUN.has(r.status) ? r : { ...r, status: 'cancelled' })),
  };
}

export function retried(detail: ScanDetail, runId: number): ScanDetail {
  return {
    ...detail,
    status: detail.status === 'done' ? 'running' : detail.status,
    runs: detail.runs.map((r) =>
      r.id === runId ? { ...r, status: 'queued', error_code: null, error_params: null } : r,
    ),
  };
}

/** Whether a result belongs in a list filtered by kind and text. */
export function matches(result: Result, kind: string | null, q: string): boolean {
  if (kind && result.entity.kind !== kind) return false;
  const text = q.trim().toLowerCase();
  if (!text) return true;
  return [result.entity.display, result.url ?? ''].some((v) => v.toLowerCase().includes(text));
}
