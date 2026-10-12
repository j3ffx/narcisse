import type {
  EntityKind,
  EntityStatus,
  ProfileKind,
  RunStatus,
  ScanStatus,
  SeedKind,
} from './types';

export const KIND_LABELS: Record<EntityKind, string> = {
  identity: 'Identité',
  name: 'Nom',
  username: 'Pseudo',
  email: 'Email',
  phone: 'Téléphone',
  address: 'Adresse',
  domain: 'Domaine',
  organization: 'Organisation',
  account: 'Compte',
  url: 'Page',
  leak: 'Fuite',
  photo: 'Photo',
};

export const SEED_KINDS: SeedKind[] = [
  'name',
  'username',
  'email',
  'phone',
  'address',
  'domain',
  'organization',
  'account',
];

/** Fictitious examples, shown as placeholders. */
export const SEED_EXAMPLES: Record<SeedKind, string> = {
  name: 'Jeanne Exemple',
  username: 'jeanne.exemple, ou @jeanne@instance.example',
  email: 'jeanne@example.org',
  phone: '+33 6 39 98 00 00',
  address: '1 rue de l’Exemple, 75000 Paris',
  domain: 'example.org',
  organization: 'Exemple SARL, ou un SIREN',
  account: 'https://forum.example.org/u/jeanne',
};

export const PROFILE_KIND_LABELS: Record<ProfileKind, string> = {
  personal: 'Perso',
  professional: 'Pro',
  mixed: 'Perso et pro',
};

export const ENTITY_STATUS_LABELS: Record<EntityStatus, string> = {
  unreviewed: 'À vérifier',
  confirmed: 'C’est moi',
  false_positive: 'Pas moi',
};

export const SCAN_STATUS_LABELS: Record<ScanStatus, string> = {
  running: 'En cours',
  paused: 'En pause',
  cancelled: 'Annulé',
  done: 'Terminé',
};

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  queued: 'En file',
  running: 'En cours',
  paused: 'En pause',
  rate_limited: 'Limité par la source',
  failed: 'En erreur',
  done: 'Terminé',
  cancelled: 'Annulé',
};

export const RELATION_LABELS: Record<string, string> = {
  declares: 'déclaré',
  has_account: 'compte',
  mentioned_on: 'mentionné sur',
  uses_email: 'utilise l’email',
  uses_username: 'utilise le pseudo',
  shows_name: 'nom affiché',
  shows_email: 'email affiché',
  links_to: 'lien',
  commits_as: 'commits',
  publishes_key: 'clé PGP publiée',
  key_identity: 'identité de la clé',
  proves: 'preuve d’identité',
  handle_domain: 'domaine du pseudo',
};

/** What a search reports, in the order it reads best. */
export const NOTE_LABELS: [string, (n: number) => string][] = [
  ['checked', (n) => `${n} vérifié${n > 1 ? 's' : ''}`],
  ['found', (n) => `${n} trouvé${n > 1 ? 's' : ''}`],
  ['uncertain', (n) => `${n} indéterminé${n > 1 ? 's' : ''}`],
  ['blocked', (n) => `${n} bloqué${n > 1 ? 's' : ''} par un anti-robot`],
  ['unreachable', (n) => `${n} injoignable${n > 1 ? 's' : ''}`],
  ['skipped', (n) => `${n} ignoré${n > 1 ? 's' : ''} (captcha)`],
  ['excluded', (n) => `${n} exclu${n > 1 ? 's' : ''} (sites adultes)`],
];

export const CATEGORY_LABELS: Record<string, string> = {
  accounts: 'Comptes',
  social: 'Réseaux sociaux',
  forums: 'Forums',
  code: 'Code',
  keys: 'Clés',
  demo: 'Démonstration',
};

export const FINISHED_RUN: ReadonlySet<RunStatus> = new Set(['failed', 'done', 'cancelled']);
export const ACTIVE_SCAN: ReadonlySet<ScanStatus> = new Set(['running', 'paused']);
