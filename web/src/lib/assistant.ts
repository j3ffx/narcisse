import { lazy, num, t } from '@/i18n';
// The assistant's words and how its answers sit in the cache. Pure functions, tested in
// assistant.test.ts.
import type { Annotation, AnnotationTask, AssistantProvider, Verdict } from './types';

export const PROVIDER_LABELS: Record<AssistantProvider, string> = lazy(
  () => t().assistant.providers,
);

/** The provider's short name, as answers name it. */
export const PROVIDER_NAMES: Record<AssistantProvider, string> = lazy(() => t().assistant.names);

export const MODEL_LABELS: Record<string, string> = lazy(() => t().assistant.models);

export const VERDICT_LABELS: Record<Verdict, string> = lazy(() => t().assistant.verdicts);

export const TASK_LABELS: Record<AnnotationTask, string> = lazy(() => t().assistant.tasks);

/** What a question waiting or under way is doing. */
export function stateText(annotation: Annotation, provider: string): string {
  if (annotation.state === 'queued') return t().assistant.queued;
  if (annotation.state === 'running') return t().assistant.running[annotation.task](provider);
  return '';
}

/** Who answered: « Claude Code · claude-haiku-5-5 ». */
export function answeredBy(annotation: Annotation): string {
  const provider = PROVIDER_NAMES[annotation.provider] ?? annotation.provider;
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

export interface LeadItem {
  kind: string;
  value: string;
  reason: string;
  dismissed?: boolean;
}

/** The leads an answer kept (read in the proofs), as the UI lists them. */
export const leadsOf = (annotation: Annotation): LeadItem[] => {
  const leads = annotation.output?.leads;
  return Array.isArray(leads) ? (leads as LeadItem[]) : [];
};

/** A download's progress, « 1,2 / 3,4 Go (35 %) », or what it waits for. */
export function pullProgress(completed: number, total: number): string {
  if (!total) return t().assistant.preparingDownload;
  const gb = (bytes: number) =>
    num(bytes / 2 ** 30, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return t().assistant.progress(gb(completed), gb(total), Math.floor((completed / total) * 100));
}
