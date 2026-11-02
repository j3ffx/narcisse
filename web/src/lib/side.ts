import { useMutation } from '@tanstack/react-query';
import { get, post } from './api';
import type { AppInfo } from './types';

const CHECK_MS = 500;
const GIVE_UP_MS = 60_000;

/** Narcisse starts again on the other side (the demo, or the user's own data); the page reloads
 * once the server answers from there. */
async function switchSide(): Promise<void> {
  const before = await get<AppInfo>('/info');
  await post('/side');
  const end = Date.now() + GIVE_UP_MS;
  while (Date.now() < end) {
    await new Promise((resolve) => setTimeout(resolve, CHECK_MS));
    try {
      if ((await get<AppInfo>('/info')).demo !== before.demo) break;
    } catch {
      // Stopped, not started again yet.
    }
  }
  window.location.assign('/');
}

export const useSwitchSide = () => useMutation({ mutationFn: switchSide });
