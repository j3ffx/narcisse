import { t } from '@/i18n';
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
        { query: exact, why: t().dorks.name },
        { query: `${exact} site:linkedin.com`, why: t().dorks.linkedin },
        { query: `${exact} (cv OR "curriculum vitae")`, why: t().dorks.cv },
        {
          query: `${exact} filetype:pdf`,
          why: t().dorks.documents,
        },
        {
          query: `${exact} (site:societe.com OR site:pappers.fr OR site:annuaire-entreprises.data.gouv.fr)`,
          why: t().dorks.registers,
        },
        {
          // i18n: kept (the words searched for, as French pages write them)
          query: `${exact} (adresse OR téléphone OR "né le" OR "née le")`,
          why: t().dorks.details,
        },
        ...organizations.map((organization) => ({
          query: `${exact} ${quoted(organization)}`,
          why: t().dorks.withOrganization(organization),
        })),
      ];
    }
    case 'username':
      return [
        { query: exact, why: t().dorks.username },
        { query: `inurl:${value}`, why: t().dorks.inUrl },
      ];
    case 'email': {
      const local = value.split('@')[0] ?? '';
      return [
        { query: exact, why: t().dorks.email },
        {
          query: `${exact} (filetype:pdf OR filetype:xls OR filetype:xlsx OR filetype:csv)`,
          why: t().dorks.emailDocuments,
        },
        ...(local.length >= 4 ? [{ query: quoted(local), why: t().dorks.local }] : []),
      ];
    }
    case 'phone':
      return [
        {
          query: phoneVariants(seed.normalized).map(quoted).join(' OR '),
          why: t().dorks.phone,
        },
      ];
    case 'domain':
      return [
        {
          query: `site:${seed.normalized}`,
          why: t().dorks.site,
        },
        { query: `${quoted(seed.normalized)} -site:${seed.normalized}`, why: t().dorks.citing },
      ];
    case 'address':
    case 'organization':
      return [{ query: exact, why: t().dorks.exact }];
    case 'account':
      return [];
  }
}
