// The UI's two languages: the catalogs, the language in use, and what follows it (dates,
// numbers, plurals). The whole app is drawn again when the language changes (App keys its tree
// by it), so a text read while drawing is always in the language in use.
import { useSyncExternalStore } from 'react';
import { en } from './en';
import { fr, type Messages } from './fr';

export type Lang = 'fr' | 'en';
export type LangChoice = Lang | 'auto';
export type { Messages };

const CATALOGS: Record<Lang, Messages> = { fr, en };
const listeners = new Set<() => void>();

/** The browser's language, when it is one of ours (English otherwise). */
export function browserLang(): Lang {
  const languages = typeof navigator === 'undefined' ? [] : (navigator.languages ?? []);
  for (const tag of [...languages, typeof navigator === 'undefined' ? '' : navigator.language]) {
    const code = (tag ?? '').slice(0, 2).toLowerCase();
    if (code === 'fr' || code === 'en') return code;
  }
  return 'en';
}

let current: Lang = browserLang();
if (typeof document !== 'undefined') document.documentElement.lang = current;

export const resolveLang = (choice: LangChoice | undefined): Lang =>
  choice === 'fr' || choice === 'en' ? choice : browserLang();

export function lang(): Lang {
  return current;
}

/** The texts in the language in use. */
export function t(): Messages {
  return CATALOGS[current];
}

export function setLang(next: Lang): void {
  if (next === current) return;
  current = next;
  if (typeof document !== 'undefined') document.documentElement.lang = next;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The language in use, as React state: a component using it is drawn again when it changes. */
export const useLang = (): Lang => useSyncExternalStore(subscribe, lang, lang);

/** The locale for dates and numbers. */
export const locale = (): string => (current === 'fr' ? 'fr-FR' : 'en-GB');

/** A number as the language writes it: « 1 234,5 » or « 1,234.5 ». */
export const num = (value: number, options?: Intl.NumberFormatOptions): string =>
  value.toLocaleString(locale(), options);

/** « s » when the count takes a plural (French: 2 and more; English: anything but 1). */
export const s = (count: number): string =>
  (current === 'fr' ? count > 1 : count !== 1) ? 's' : '';

/** One word or the other, by the count. */
export const plural = (count: number, one: string, many: string): string =>
  (current === 'fr' ? count > 1 : count !== 1) ? many : one;

/** A table whose entries are read in the language in use, each time (keeps `TABLE[key]`). */
export function lazy<T extends object>(get: () => T): T {
  return new Proxy({} as T, {
    get: (_, key) => (get() as Record<PropertyKey, unknown>)[key],
    has: (_, key) => key in get(),
    ownKeys: () => Reflect.ownKeys(get()),
    getOwnPropertyDescriptor: (_, key) => {
      const value = (get() as Record<PropertyKey, unknown>)[key];
      return value === undefined ? undefined : { value, enumerable: true, configurable: true };
    },
  });
}
