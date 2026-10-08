import { ApiError } from './api';
import { KIND_LABELS } from './labels';
import type { EntityKind, Params } from './types';

const host = (p: Params) => (typeof p.host === 'string' ? p.host : 'La source');

/** The sentence shown for an error code (the server never sends text, only codes). */
const MESSAGES: Record<string, (p: Params) => string> = {
  offline: () => 'Narcisse ne répond pas. Est-il toujours lancé ?',
  internal_error: () => 'Erreur inattendue. Le détail est dans le journal de Narcisse.',
  not_found: () => 'Introuvable : peut-être supprimé entre-temps.',
  invalid_request: () => 'Certaines valeurs ne sont pas valides.',
  invalid_value: (p) =>
    `Ce ${(KIND_LABELS[p.kind as EntityKind] ?? 'champ').toLowerCase()} n’a pas l’air valide.`,
  invalid_seed_kind: () => 'Ce type d’élément ne peut pas servir de point de départ.',
  seed_exists: () => 'Cet élément est déjà dans le profil.',
  profile_busy: () => 'Un scan de ce profil est en cours : annule-le avant de supprimer le profil.',
  no_seeds: () => 'Ajoute au moins un élément à surveiller avant de lancer un scan.',
  nothing_to_scan: () => 'Aucune des sources choisies ne sait traiter les éléments de ce profil.',
  unknown_module: () => 'Une des sources choisies n’existe plus.',
  scan_not_running: () => 'Ce scan n’est plus en cours.',
  scan_not_paused: () => 'Ce scan n’est pas en pause.',
  scan_finished: () => 'Ce scan est déjà terminé.',
  run_not_retryable: () => 'Cette recherche ne peut pas être relancée.',
  forbidden_host: () => 'Requête refusée : adresse inattendue.',
  forbidden_origin: () => 'Requête refusée : elle ne vient pas de Narcisse.',
  json_required: () => 'Requête refusée : format inattendu.',
  // Module errors
  rate_limited: (p) => `${host(p)} demande de patienter.`,
  network_error: (p) => `${host(p)} est injoignable (réseau).`,
  source_timeout: (p) => `${host(p)} met trop de temps à répondre.`,
  source_error: (p) => `${host(p)} a répondu par une erreur${p.status ? ` (${p.status})` : ''}.`,
  source_unavailable: (p) => `${host(p)} est indisponible pour le moment.`,
  source_refused: (p) => `${host(p)} a refusé la demande${p.status ? ` (${p.status})` : ''}.`,
  input_rejected: () => 'Cette source ne sait pas traiter cet élément.',
  module_crashed: () => 'Le module a rencontré un bug. Le détail est dans le journal.',
  module_unavailable: () => 'Ce module n’est plus disponible (mode démo désactivé ?).',
};

export function messageFor(code: string, params: Params = {}): string {
  return MESSAGES[code]?.(params) ?? `Erreur inattendue (${code}).`;
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? messageFor(error.code, error.params)
    : messageFor('internal_error');
}
