import { t } from '@/i18n';
/** The views of a profile, as the address names them (and the tab shows them). */
export type ProfileTab = 'graphe' | 'liste' | 'elements' | 'recherche' | 'a-faire' | 'scans';

const KEYS: ProfileTab[] = ['graphe', 'liste', 'elements', 'recherche', 'a-faire', 'scans'];

/** The tabs and their titles, in the language in use. */
export const tabs = (): [ProfileTab, string][] => KEYS.map((key) => [key, t().tabs[key]]);

export const isProfileTab = (value: string): value is ProfileTab =>
  KEYS.includes(value as ProfileTab);
