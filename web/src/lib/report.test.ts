import { describe, expect, it } from 'vitest';
import { escapeHtml, exportName, toCsv, toReport, type ProfileExport } from './report';

const trace = (over: Record<string, unknown>) => ({
  id: 2,
  kind: 'url',
  display: 'https://annuaire.example.org/jeanne',
  normalized: 'https://annuaire.example.org/jeanne',
  status: 'unreviewed',
  confidence: 0.8,
  risk: 0.55,
  attributes: {},
  gone_at: null,
  first_seen: '2026-10-01T10:00:00Z',
  last_seen: '2026-10-20T10:00:00Z',
  modules: ['searxng'],
  evidence_count: 2,
  reasons: { confidence: [], risk: [{ code: 'kind', points: 20, params: { kind: 'url' } }] },
  ...over,
});

const data = {
  format: 'narcisse-export',
  version: 1,
  narcisse: '0.1.0',
  exported_at: '2026-10-27T10:00:00Z',
  profile: { id: 1, name: 'Jeanne Exemple', kind: 'personal', seeds: [] },
  exposure: { levels: { low: 0, medium: 0, high: 1, critical: 0 }, exposure: 0.55 },
  traces: [
    trace({ id: 1, kind: 'identity', display: 'Jeanne Exemple', modules: [] }),
    trace({}),
    trace({ id: 3, display: 'Une "page"; avec <balise>', status: 'false_positive' }),
    trace({ id: 4, display: 'Une <b>vraie</b>; "page"', risk: 0.1 }),
  ],
  evidence: [{ entity_id: 2, url: 'https://annuaire.example.org/jeanne' }],
  requests: [],
  history: [],
} as unknown as ProfileExport;

const title = (m: string) => (m === 'searxng' ? 'Recherche web (SearXNG)' : m);

describe('exports', () => {
  it('names the file after the profile and the day', () => {
    expect(exportName(data, 'csv')).toBe('narcisse-jeanne-exemple-2026-10-27.csv');
  });

  it('writes the user’s traces as CSV for a French spreadsheet', () => {
    const csv = toCsv(data, title);
    expect(csv.startsWith('\uFEFFType;Trace;Statut')).toBe(true);
    const lines = csv.trim().split('\r\n');
    expect(lines).toHaveLength(3); // header, two traces: no identity, no "not me"
    expect(lines[1]).toBe(
      'Page;https://annuaire.example.org/jeanne;À vérifier;80;55;élevé;Recherche web (SearXNG);2026-10-01;2026-10-20;;2;https://annuaire.example.org/jeanne;',
    );
    expect(lines[2]).toContain('"Une <b>vraie</b>; ""page"""');
  });

  it('writes a report with no script and nothing unescaped', () => {
    const html = toReport(data, title);
    expect(html).not.toMatch(/<script|src=|href=/i);
    expect(html).toContain('Une &lt;b&gt;vraie&lt;/b&gt;; &quot;page&quot;');
    expect(html).toContain('Ce qu’Internet sait de Jeanne Exemple');
    expect(html).not.toContain('balise');
  });

  it('escapes every special character', () => {
    expect(escapeHtml(`<a href="x">'&'</a>`)).toBe(
      '&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;',
    );
  });
});
