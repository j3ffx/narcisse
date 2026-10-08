import type { EntityKind, ProfileKind, RunStatus, ScanStatus, SeedKind } from './types';

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
  username: 'jeanne.exemple',
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
};

export const FINISHED_RUN: ReadonlySet<RunStatus> = new Set(['failed', 'done', 'cancelled']);
export const ACTIVE_SCAN: ReadonlySet<ScanStatus> = new Set(['running', 'paused']);
