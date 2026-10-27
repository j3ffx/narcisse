// Where a launch of the user's SearXNG from the app is, as the UI says it.
import { messageFor } from './errors';
import type { SearxngStatus } from './types';

const LAUNCH_STEPS: Record<string, string> = {
  desktop: 'Démarrage de Docker Desktop (ça peut prendre une minute)…',
  compose: 'Lancement de SearXNG avec Docker…',
  waiting: 'Attente de la première réponse de SearXNG…',
};

/** Where a launch of SearXNG from the app is, in a sentence (empty when there's nothing to say). */
export function launchState(status: SearxngStatus | undefined): string {
  if (!status) return '';
  if (status.state === 'starting') return LAUNCH_STEPS[status.step ?? ''] ?? 'Lancement…';
  if (status.state === 'ready') return 'C’est prêt.';
  if (status.state === 'failed' && status.error) return messageFor(status.error);
  if (!status.docker) return 'Docker n’est pas installé : installe Docker Desktop, puis réessaie.';
  return '';
}
