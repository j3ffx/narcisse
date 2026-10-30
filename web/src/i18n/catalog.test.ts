import { afterEach, describe, expect, it } from 'vitest';
import { en } from './en';
import { fr } from './fr';
import { lang, num, plural, s, setLang } from './index';

// Every source file of the UI, as text (the catalogs and the tests left out).
const SOURCES = Object.entries(
  import.meta.glob<string>(['../**/*.{ts,tsx}', '!./**', '!../**/*.test.ts'], {
    query: '?raw',
    import: 'default',
    eager: true,
  }),
);
// French letters and typography: a text written in French in the code, not in a catalog.
const FRENCH = /[éèàùçêôîœâû’«»]/i;

/** The lines of a file that are code, comments left out (block and line comments). */
function code(text: string): string[] {
  const lines: string[] = [];
  let inBlock = false;
  let kept = false;
  for (const line of text.split('\n')) {
    // A line said to be kept on purpose (words searched for, say): the one after the marker.
    if (kept || line.includes('i18n: kept')) {
      kept = !kept;
      lines.push('');
      continue;
    }
    let rest = line;
    if (inBlock) {
      const end = rest.indexOf('*/');
      if (end === -1) continue;
      rest = rest.slice(end + 2);
      inBlock = false;
    }
    rest = rest.replace(/\/\*.*?\*\//g, '');
    const start = rest.indexOf('/*');
    if (start !== -1) {
      inBlock = true;
      rest = rest.slice(0, start);
    }
    const comment = rest.search(/(^|\s)\/\/\s/);
    if (comment !== -1) rest = rest.slice(0, comment);
    lines.push(rest);
  }
  return lines;
}

function keys(value: unknown, path = ''): string[] {
  if (Array.isArray(value)) return [`${path}[${value.length}]`];
  if (value && typeof value === 'object')
    return Object.entries(value).flatMap(([key, inner]) => keys(inner, `${path}.${key}`));
  return [`${path}:${typeof value}`];
}

describe('the UI’s texts', () => {
  afterEach(() => setLang('fr'));

  it('are all in the catalogs: no French left in the code', () => {
    expect(SOURCES.length).toBeGreaterThan(50);
    const found = SOURCES.flatMap(([path, text]) =>
      code(text)
        .map((line, index) => ({ line, index }))
        // A language named in its own words, for whoever reads that language.
        .filter(({ line }) => FRENCH.test(line) && !line.includes("'Français'"))
        .map(({ line, index }) => `${path}:${index + 1}: ${line.trim()}`),
    );
    expect(found).toEqual([]);
  });

  it('have the same shape in French and in English', () => {
    expect(keys(en)).toEqual(keys(fr));
  });

  it('follow the language for plurals and numbers', () => {
    setLang('fr');
    expect([s(0), s(1), s(2)]).toEqual(['', '', 's']);
    expect(plural(1, 'trace', 'traces')).toBe('trace');
    expect(num(1234.5).replace(/\s/g, ' ')).toBe('1 234,5');
    setLang('en');
    expect(lang()).toBe('en');
    expect([s(0), s(1), s(2)]).toEqual(['s', '', 's']);
    expect(num(1234.5)).toBe('1,234.5');
  });
});
