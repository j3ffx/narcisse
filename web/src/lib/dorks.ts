import type { Seed } from './types';

/** A search engine the user opens themselves: Narcisse never asks one. */
export interface SearchEngine {
  name: string;
  url: (query: string) => string;
}

const searchUrl = (base: string) => (query: string) => `${base}${encodeURIComponent(query)}`;

export const ENGINES: SearchEngine[] = [
  { name: 'Google', url: searchUrl('https://www.google.com/search?q=') },
  { name: 'Bing', url: searchUrl('https://www.bing.com/search?q=') },
  { name: 'DuckDuckGo', url: searchUrl('https://duckduckgo.com/?q=') },
  { name: 'Qwant', url: searchUrl('https://www.qwant.com/?q=') },
];

export interface AssistedQuery {
  query: string;
  /** What it looks for, in a few words. */
  why: string;
}

const quoted = (value: string) => `"${value.replaceAll('"', '')}"`;

/** A French number as people write it: 06 39 98 00 00, 06.39.98.00.00, +33 6 39 98 00 00… */
export function phoneVariants(normalized: string): string[] {
  const digits = normalized.replace(/[^\d+]/g, '');
  const national = digits.startsWith('+33')
    ? `0${digits.slice(3)}`
    : /^0\d{9}$/.test(digits)
      ? digits
      : null;
  if (national === null) return [digits];
  const pairs = national.match(/\d{2}/g) ?? [];
  const rest = national.slice(1);
  return [
    pairs.join(' '),
    national,
    pairs.join('.'),
    `+33 ${rest[0]} ${rest.slice(1).match(/\d{2}/g)?.join(' ') ?? ''}`,
    `+33${rest}`,
  ];
}

/** The searches worth making by hand for one of the profile's elements. */
export function queriesFor(seed: Seed, all: readonly Seed[]): AssistedQuery[] {
  const value = seed.value.trim();
  const exact = quoted(value);
  switch (seed.kind) {
    case 'name': {
      const organizations = all
        .filter((s) => s.kind === 'organization' && !/^\d+$/.test(s.normalized))
        .map((s) => s.value.trim());
      return [
        { query: exact, why: 'Les pages qui citent ce nom exact.' },
        { query: `${exact} site:linkedin.com`, why: 'Ton profil LinkedIn, et ceux qui te citent.' },
        { query: `${exact} (cv OR "curriculum vitae")`, why: 'Un CV en ligne.' },
        {
          query: `${exact} filetype:pdf`,
          why: 'Des documents : comptes rendus, annuaires, listes de participants…',
        },
        {
          query: `${exact} (site:societe.com OR site:pappers.fr OR site:annuaire-entreprises.data.gouv.fr)`,
          why: 'Les registres d’entreprises : dirigeant, associé, auto-entrepreneur.',
        },
        {
          query: `${exact} (adresse OR téléphone OR "né le" OR "née le")`,
          why: 'Des coordonnées, une date de naissance.',
        },
        ...organizations.map((organization) => ({
          query: `${exact} ${quoted(organization)}`,
          why: `Ce nom avec ${organization}.`,
        })),
      ];
    }
    case 'username':
      return [
        { query: exact, why: 'Les pages qui citent ce pseudo.' },
        { query: `inurl:${value}`, why: 'Les adresses qui le contiennent : des profils, souvent.' },
      ];
    case 'email': {
      const local = value.split('@')[0] ?? '';
      return [
        { query: exact, why: 'Les pages qui citent cette adresse.' },
        {
          query: `${exact} (filetype:pdf OR filetype:xls OR filetype:xlsx OR filetype:csv)`,
          why: 'Des documents et des listes qui la contiennent.',
        },
        ...(local.length >= 4
          ? [{ query: quoted(local), why: 'Ce qui précède le @ : souvent un pseudo.' }]
          : []),
      ];
    }
    case 'phone':
      return [
        {
          query: phoneVariants(seed.normalized).map(quoted).join(' OR '),
          why: 'Ce numéro, écrit de plusieurs façons.',
        },
      ];
    case 'domain':
      return [
        {
          query: `site:${seed.normalized}`,
          why: 'Les pages du site que les moteurs gardent, oubliées comprises.',
        },
        { query: `${quoted(seed.normalized)} -site:${seed.normalized}`, why: 'Qui cite ce site.' },
      ];
    case 'address':
    case 'organization':
      return [{ query: exact, why: 'Les pages qui citent exactement ceci.' }];
    case 'account':
      return [];
  }
}
