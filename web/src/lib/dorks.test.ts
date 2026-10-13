import { describe, expect, it } from 'vitest';
import { ENGINES, phoneVariants, queriesFor } from './dorks';
import type { Seed, SeedKind } from './types';

const seed = (kind: SeedKind, value: string, normalized = value.toLowerCase()): Seed => ({
  id: 1,
  profile_id: 1,
  kind,
  value,
  normalized,
  status: 'watch',
  created_at: '2026-10-13T12:00:00Z',
});

describe('assisted search', () => {
  it('looks for a name in documents, registries and with the profile’s organizations', () => {
    const name = seed('name', 'Jeanne Exemple');
    const queries = queriesFor(name, [
      name,
      seed('organization', 'Exemple SARL'),
      seed('organization', '123456782'),
    ]).map((q) => q.query);
    expect(queries[0]).toBe('"Jeanne Exemple"');
    expect(queries).toContain('"Jeanne Exemple" filetype:pdf');
    expect(queries).toContain('"Jeanne Exemple" "Exemple SARL"');
    // A SIREN alone isn't a name to search with.
    expect(queries.some((q) => q.includes('123456782'))).toBe(false);
  });

  it('writes a French number the ways people write it', () => {
    expect(phoneVariants('+33639980000')).toEqual([
      '06 39 98 00 00',
      '0639980000',
      '06.39.98.00.00',
      '+33 6 39 98 00 00',
      '+33639980000',
    ]);
    expect(phoneVariants('0639980000')[0]).toBe('06 39 98 00 00');
    expect(phoneVariants('+4930123456')).toEqual(['+4930123456']);
    expect(queriesFor(seed('phone', '06 39 98 00 00', '0639980000'), [])[0]?.query).toContain(
      '"+33 6 39 98 00 00" OR "+33639980000"',
    );
  });

  it('searches a domain inside and outside of itself, an address and what precedes its @', () => {
    expect(queriesFor(seed('domain', 'jeanne-exemple.fr'), []).map((q) => q.query)).toEqual([
      'site:jeanne-exemple.fr',
      '"jeanne-exemple.fr" -site:jeanne-exemple.fr',
    ]);
    expect(queriesFor(seed('email', 'jeanne.exemple@example.org'), []).at(-1)?.query).toBe(
      '"jeanne.exemple"',
    );
    expect(queriesFor(seed('account', 'https://forum.example.org/u/jeanne'), [])).toEqual([]);
  });

  it('opens the engines with the query, encoded', () => {
    expect(ENGINES.map((e) => e.url('"Jeanne Exemple" filetype:pdf'))).toContain(
      'https://duckduckgo.com/?q=%22Jeanne%20Exemple%22%20filetype%3Apdf',
    );
  });
});
