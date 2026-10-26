// How sure a trace is (confidence) and how much it exposes (risk), as the user reads them: the
// reasons the API gives (engine/scoring.py) said in French, and the risk levels. Pure functions,
// tested in scores.test.ts.
import { KIND_LABELS } from './labels';
import type { EntityKind, ScoreReason } from './types';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

/** Floors of each level, on the 0..1 scale (the same as the API's). */
export const RISK_FLOORS: [number, RiskLevel][] = [
  [0.75, 'critical'],
  [0.5, 'high'],
  [0.25, 'medium'],
  [0, 'low'],
];

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  low: 'faible',
  medium: 'moyen',
  high: 'élevé',
  critical: 'critique',
};

export function riskLevel(risk: number): RiskLevel {
  return RISK_FLOORS.find(([floor]) => risk >= floor)?.[1] ?? 'low';
}

/** A 0..1 score as the UI shows it, 0 to 100. */
export const points = (score: number) => Math.round(score * 100);

type Text = (params: Record<string, unknown>) => string;
const str = (value: unknown) => (typeof value === 'string' ? value : '');

const TEXTS: Record<string, Text> = {
  // Confidence
  identity: () => 'C’est toi : le point de départ du profil.',
  declared: () => 'Un élément que tu as déclaré.',
  confirmed: () => 'Tu as dit « c’est moi ».',
  rejected: () => 'Tu as dit « pas moi ».',
  sources: () => 'Ce qu’en dit la source qui l’a trouvée.',
  no_source_confidence: () =>
    'La source n’a pas dit à quel point elle est sûre : une chance sur deux.',
  several_sources: (p) => `Trouvée par ${String(p.count)} sources indépendantes.`,
  corroborated: (p) =>
    `Elle relie ${String(p.count)} de tes éléments ou traces confirmées entre eux.`,
  via_confirmed: (p) => `Trouvée à partir d’une trace que tu as confirmée (${str(p.trace)}).`,
  via_rejected: () => 'Trouvée seulement à partir de traces que tu as rejetées.',
  unreviewed_cap: () => 'Pas encore triée : au plus 95 tant que tu ne l’as pas confirmée.',
  // Risk
  identity_risk: () => 'Ton identité elle-même n’est pas une trace.',
  not_public: () => 'Trouvé nulle part en public pour l’instant.',
  kind: (p) => `${KIND_LABELS[str(p.kind) as EntityKind] ?? 'Trace'} : exposition de base.`,
  leaked_passwords: () => 'Les mots de passe de cette fuite sont lisibles.',
  leaked_identity: () => 'Cette fuite contient des pièces d’identité ou des données bancaires.',
  birth_published: () => 'Le registre publie un mois et une année de naissance.',
  adult_site: () => 'Un compte sur un site adulte.',
  data_broker: (p) =>
    `Une fiche chez ${str(p.source) || 'un courtier en données'}, qui revend des contacts.`,
  expected_professional: () =>
    'Attendu en public pour un profil pro (ton entreprise, ton domaine, le registre) : compte moitié moins.',
  movements: () => 'Ce site peut montrer tes déplacements.',
  sensitive_subdomain: (p) =>
    `Le sous-domaine « ${str(p.label)} » désigne un accès à tes machines ou à tes fichiers.`,
  registry_contact: () => 'Une coordonnée que le registre d’un domaine publie.',
  archived: () => 'Une archive du web en garde une copie.',
  weighted: () => 'Pondéré par la confiance : une trace qui n’est peut-être pas toi compte moins.',
};

/** What a rule means, in a sentence. */
export function reasonText(reason: ScoreReason): string {
  return TEXTS[reason.code]?.(reason.params ?? {}) ?? reason.code;
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
  if (reason.factor != null) return `×${reason.factor.toLocaleString('fr-FR')}`;
  if (reason.points == null) return '';
  if (SETS.has(reason.code)) return String(reason.points);
  return reason.points < 0 ? `−${-reason.points}` : `+${reason.points}`;
}
