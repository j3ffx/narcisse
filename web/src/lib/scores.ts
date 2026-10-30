import { lazy, num, t } from '@/i18n';
// How sure a trace is (confidence) and how much it exposes (risk), as the user reads them: the
// reasons the API gives (engine/scoring.py) said in a sentence, and the risk levels. Pure functions,
// tested in scores.test.ts.
import type { ScoreReason } from './types';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

/** Floors of each level, on the 0..1 scale (the same as the API's). */
export const RISK_FLOORS: [number, RiskLevel][] = [
  [0.75, 'critical'],
  [0.5, 'high'],
  [0.25, 'medium'],
  [0, 'low'],
];

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = lazy(() => t().risk.levels);

export function riskLevel(risk: number): RiskLevel {
  return RISK_FLOORS.find(([floor]) => risk >= floor)?.[1] ?? 'low';
}

/** A 0..1 score as the UI shows it, 0 to 100. */
export const points = (score: number) => Math.round(score * 100);

/** What a rule means, in a sentence. */
export function reasonText(reason: ScoreReason): string {
  return t().risk.reasons[reason.code]?.(reason.params ?? {}) ?? reason.code;
}

// Rules that set a value (or a starting point) rather than add to it.
const SETS = new Set([
  'identity',
  'declared',
  'confirmed',
  'rejected',
  'sources',
  'no_source_confidence',
  'unreviewed_cap',
  'identity_risk',
  'not_public',
  'kind',
]);

/** What a rule did to the score: « 60 », « +15 », « ×0,7 ». */
export function reasonEffect(reason: ScoreReason): string {
  if (reason.factor != null) return `×${num(reason.factor)}`;
  if (reason.points == null) return '';
  if (SETS.has(reason.code)) return String(reason.points);
  return reason.points < 0 ? `−${-reason.points}` : `+${reason.points}`;
}
