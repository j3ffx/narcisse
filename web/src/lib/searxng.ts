import { t } from '@/i18n';
// Where a launch of the user's SearXNG from the app is, as the UI says it.
import { messageFor } from './errors';
import type { SearxngStatus } from './types';

/** Where a launch of SearXNG from the app is, in a sentence (empty when there's nothing to say). */
export function launchState(status: SearxngStatus | undefined): string {
  if (!status) return '';
  const say = t().searxng;
  if (status.state === 'starting') return say.steps[status.step ?? ''] ?? say.starting;
  if (status.state === 'ready') return say.ready;
  if (status.state === 'failed' && status.error) return messageFor(status.error);
  if (!status.docker) return say.noDocker;
  return '';
}
