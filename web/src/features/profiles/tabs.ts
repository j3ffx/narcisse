/** The views of a profile, as the address names them (and the tab shows them). */
export type ProfileTab = 'graphe' | 'liste' | 'elements' | 'recherche' | 'a-faire' | 'scans';

export const TABS: [ProfileTab, string][] = [
  ['graphe', 'Graphe'],
  ['liste', 'Liste'],
  ['elements', 'Éléments'],
  ['recherche', 'Recherche'],
  ['a-faire', 'À faire'],
  ['scans', 'Scans'],
];

export const isProfileTab = (value: string): value is ProfileTab =>
  TABS.some(([key]) => key === value);
