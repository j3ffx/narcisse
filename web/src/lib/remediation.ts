import { lazy, locale, t } from '@/i18n';
// What the user can do about a trace, as the action sheet says it: the actions the API picks
// (remediation/actions.py) explained in a sentence, the difficulty the knowledge base gives, and the
// e-mail link that opens a prepared request in the user's own mail client. Pure functions,
// tested in remediation.test.ts.
import type { Difficulty, FollowedRequest, RequestStatus } from './types';

export interface ActionText {
  title: string;
  what: string;
}

export const ACTION_TEXTS: Record<string, ActionText> = lazy(() => t().actions);

export function actionText(code: string): ActionText {
  return ACTION_TEXTS[code] ?? { title: code, what: '' };
}

export const DIFFICULTY_LABELS: Record<Difficulty, string> = lazy(() => t().difficulty);

export const LETTER_LABELS: Record<string, string> = lazy(() => t().letterKinds);

/** Past this length, some mail clients cut the link: the text goes through the clipboard. */
export const MAILTO_LIMIT = 1800;

/** A `mailto:` link with the recipient, the subject and (when it fits) the body. Line breaks
 * are CRLF, as RFC 6068 asks. */
export function mailtoHref(to: string, subject: string, body: string): string {
  const enc = (text: string) => encodeURIComponent(text.replace(/\r?\n/g, '\r\n'));
  const head = `mailto:${enc(to.trim()).replace(/%40/g, '@')}?subject=${enc(subject)}`;
  const full = `${head}&body=${enc(body)}`;
  return full.length <= MAILTO_LIMIT ? full : head;
}

/** The letter as one text, to paste anywhere (« Objet : » or « Subject: », by its language). */
export const letterText = (subject: string, body: string, language: 'fr' | 'en' = 'fr') =>
  subject ? `${language === 'en' ? 'Subject:' : 'Objet :'} ${subject}\n\n${body}` : body;

export const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = lazy(() => t().requestStatus);

/** What the last scan that looked for the trace again saw, in a sentence. */
export function checkText(request: FollowedRequest): string | null {
  if (!request.check || !request.checked_at) return null;
  const when = formatDay(request.checked_at);
  return request.check === 'gone' ? t().requests.gone(when) : t().requests.stillThere(when);
}

/** Where a followed request stands, in a few words. */
export function requestSummary(request: FollowedRequest): string {
  const say = t().requests;
  const sent = request.sent_at ? say.sentOn(formatDay(request.sent_at)) : null;
  const parts =
    request.status === 'sent' && sent
      ? [say.sentOnCap(formatDay(request.sent_at!))]
      : [REQUEST_STATUS_LABELS[request.status], ...(sent ? [sent] : [])];
  if (request.reminded_at) parts.push(say.remindedOn(formatDay(request.reminded_at)));
  if (request.due) parts.push(say.toRemind);
  else if (request.reminder_at && request.status !== 'done')
    parts.push(say.reminderFrom(formatDay(request.reminder_at)));
  return parts.join(' · ');
}

export const formatDay = (iso: string) =>
  new Date(iso).toLocaleDateString(locale(), { day: 'numeric', month: 'long', year: 'numeric' });
