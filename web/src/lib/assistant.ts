// The assistant's words and how its answers sit in the cache. Pure functions, tested in
// assistant.test.ts.
import type { Annotation, AnnotationTask, AssistantProvider, Verdict } from './types';

export const PROVIDER_LABELS: Record<AssistantProvider, string> = {
  none: 'Aucun',
  claude_code: 'Claude Code',
  local: 'Un modèle sur ta machine',
  openai: 'Un autre service compatible OpenAI',
  demo: 'Assistant de démonstration',
};

/** The provider's short name, as answers name it. */
export const PROVIDER_NAMES: Record<AssistantProvider, string> = {
  ...PROVIDER_LABELS,
  local: 'Le modèle local',
  openai: 'Le service',
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
  leads: 'Chercher des pistes',
  letter: 'Adapter la lettre',
};

/** What a question waiting or under way is doing. */
export function stateText(annotation: Annotation, provider: string): string {
  if (annotation.state === 'queued') return 'En attente de son tour…';
  if (annotation.state === 'running')
    return {
      triage: `${provider} compare la trace à ce que tu as déclaré…`,
      explain: `${provider} lit la trace et ses preuves…`,
      leads: `${provider} cherche des pistes dans les preuves…`,
      letter: `${provider} réécrit la lettre…`,
    }[annotation.task];
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
  if (!total) return 'Préparation du téléchargement…';
  const gb = (bytes: number) =>
    (bytes / 2 ** 30).toLocaleString('fr-FR', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
  return `${gb(completed)} / ${gb(total)} Go (${Math.floor((completed / total) * 100)} %)`;
}
