// The assistant's words and how its answers sit in the cache. Pure functions, tested in
// assistant.test.ts.
import type { Annotation, AnnotationTask, AssistantProvider, Verdict } from './types';

export const PROVIDER_LABELS: Record<AssistantProvider, string> = {
  none: 'Aucun',
  claude_code: 'Claude Code',
  demo: 'Assistant de démonstration',
};

export const MODEL_LABELS: Record<string, string> = {
  haiku: 'Haiku (rapide, économe)',
  sonnet: 'Sonnet (plus fin, plus lent)',
  opus: 'Opus (le plus fin, le plus lent)',
};

export const VERDICT_LABELS: Record<Verdict, string> = {
  me: 'C’est sans doute toi',
  not_me: 'Ce n’est sans doute pas toi',
  unsure: 'Impossible à dire',
};

export const TASK_LABELS: Record<AnnotationTask, string> = {
  triage: 'Est-ce bien moi ?',
  explain: 'Expliquer cette trace',
};

/** What a question waiting or under way is doing. */
export function stateText(annotation: Annotation, provider: string): string {
  if (annotation.state === 'queued') return 'En attente de son tour…';
  if (annotation.state === 'running')
    return annotation.task === 'triage'
      ? `${provider} compare la trace à ce que tu as déclaré…`
      : `${provider} lit la trace et ses preuves…`;
  return '';
}

/** Who answered: « Claude Code · claude-haiku-5-5 ». */
export function answeredBy(annotation: Annotation): string {
  const provider = PROVIDER_LABELS[annotation.provider] ?? annotation.provider;
  return annotation.model ? `${provider} · ${annotation.model}` : provider;
}

/** The latest question of a kind about a trace (the list comes latest first). */
export function latest(annotations: Annotation[], task: AnnotationTask): Annotation | undefined {
  return annotations.find((a) => a.task === task);
}

export const isBusy = (annotation: Annotation | undefined) =>
  annotation?.state === 'queued' || annotation?.state === 'running';

/** A trace's annotations with this one added or replaced, latest first. */
export function withAnnotation(list: Annotation[], annotation: Annotation): Annotation[] {
  const others = list.filter((a) => a.id !== annotation.id);
  return [...others, annotation].sort((a, b) => b.id - a.id);
}

export const verdictOf = (annotation: Annotation): Verdict | null => {
  const verdict = annotation.output?.verdict;
  return verdict === 'me' || verdict === 'not_me' || verdict === 'unsure' ? verdict : null;
};

export const textOf = (annotation: Annotation, field: string): string => {
  const value = annotation.output?.[field];
  return typeof value === 'string' ? value : '';
};
