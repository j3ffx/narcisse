import { useEffect, useState } from 'react';
import type { Run } from './types';

/** The current time, refreshed every `interval` ms (for countdowns and ETAs). */
export function useNow(interval = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), interval);
    return () => clearInterval(timer);
  }, [interval]);
  return now;
}

/** « 45 s », « 3 min », « 1 h 05 ». */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const minutes = Math.round(s / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`;
}

// Where each running run was when this page first saw it progress: the pace is measured from
// there, so that pauses, rate limits, retries and restarts don't skew the estimate.
const paces = new Map<number, { at: number; done: number }>();

/** Seconds left for a running run, from the pace seen so far; null until it can be told. */
export function remainingSeconds(run: Run, now: number): number | null {
  const { progress_done: done, progress_total: total } = run;
  if (run.status !== 'running' || done === null || !total || done >= total) {
    paces.delete(run.id);
    return null;
  }
  const start = paces.get(run.id);
  if (!start || done < start.done) {
    paces.set(run.id, { at: now, done });
    return null;
  }
  if (done === start.done || now <= start.at) return null;
  return ((now - start.at) / 1000 / (done - start.done)) * (total - done);
}

/** Seconds until a moment, never negative. */
export function secondsUntil(iso: string, now: number): number {
  return Math.max(0, (Date.parse(iso) - now) / 1000);
}

const DATE = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });

export function formatDate(iso: string): string {
  return DATE.format(new Date(iso));
}
