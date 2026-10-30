import { describe, expect, it } from 'vitest';
import { answeredBy, isBusy, latest, stateText, verdictOf, withAnnotation } from './assistant';
import type { Annotation } from './types';

const note = (over: Partial<Annotation> = {}): Annotation => ({
  id: 1,
  entity_id: 7,
  task: 'triage',
  provider: 'claude_code',
  model: 'claude-haiku-5-5',
  prompt: '…',
  output: { verdict: 'not_me', reason: 'Une autre ville.' },
  edited: false,
  state: 'done',
  error_code: null,
  error_params: null,
  decision: 'pending',
  created_at: '2026-10-30T10:00:00Z',
  finished_at: '2026-10-30T10:00:05Z',
  ...over,
});

describe('the assistant’s answers', () => {
  it('keeps a trace’s annotations latest first, replacing an updated one', () => {
    const list = [note({ id: 3 }), note({ id: 1 })];
    const updated = withAnnotation(list, note({ id: 3, state: 'running' }));
    expect(updated.map((a) => [a.id, a.state])).toEqual([
      [3, 'running'],
      [1, 'done'],
    ]);
    expect(withAnnotation(list, note({ id: 4 })).map((a) => a.id)).toEqual([4, 3, 1]);
  });

  it('finds the latest question of a kind', () => {
    const list = [note({ id: 3, task: 'explain' }), note({ id: 2 }), note({ id: 1 })];
    expect(latest(list, 'triage')?.id).toBe(2);
    expect(latest(list, 'explain')?.id).toBe(3);
    expect(latest([], 'triage')).toBeUndefined();
  });

  it('reads a verdict only when it is one', () => {
    expect(verdictOf(note())).toBe('not_me');
    expect(verdictOf(note({ output: { verdict: 'peut-être' } }))).toBeNull();
    expect(verdictOf(note({ output: null }))).toBeNull();
  });

  it('says who answered and what a pending question is doing', () => {
    expect(answeredBy(note())).toBe('Claude Code · claude-haiku-5-5');
    expect(answeredBy(note({ provider: 'demo', model: null }))).toBe('Assistant de démonstration');
    expect(stateText(note({ state: 'queued' }), 'Claude Code')).toBe('En attente de son tour…');
    expect(stateText(note({ state: 'running' }), 'Claude Code')).toMatch(/^Claude Code compare/);
    expect(isBusy(note({ state: 'running' }))).toBe(true);
    expect(isBusy(note())).toBe(false);
    expect(isBusy(undefined)).toBe(false);
  });
});
