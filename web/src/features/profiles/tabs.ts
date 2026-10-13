/** The views of a profile, as the address names them (and the tab shows them). */
export type ProfileTab = 'graphe' | 'liste' | 'elements' | 'recherche' | 'scans';

export const TABS: [ProfileTab, string][] = [
  ['graphe', 'Graphe'],
  ['liste', 'Liste'],
  ['elements', 'Éléments'],
  ['recherche', 'Recherche'],
  ['scans', 'Scans'],
];

export const isProfileTab = (value: string): value is ProfileTab =>
  TABS.some(([key]) => key === value);
