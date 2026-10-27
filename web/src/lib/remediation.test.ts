import { describe, expect, it } from 'vitest';
import {
  MAILTO_LIMIT,
  actionText,
  checkText,
  letterText,
  mailtoHref,
  requestSummary,
} from './remediation';
import type { FollowedRequest } from './types';

describe('mailtoHref', () => {
  it('keeps the address readable and encodes the rest with CRLF line breaks', () => {
    const href = mailtoHref(' info@example.org ', 'Objet é', 'Ligne 1\nLigne 2');
    expect(href).toBe(
      'mailto:info@example.org?subject=Objet%20%C3%A9&body=Ligne%201%0D%0ALigne%202',
    );
  });

  it('leaves the recipient empty when it is unknown', () => {
    expect(mailtoHref('', 'Sujet', 'Texte')).toBe('mailto:?subject=Sujet&body=Texte');
  });

  it('drops a body too long for a link', () => {
    const href = mailtoHref('info@example.org', 'Sujet', 'é'.repeat(MAILTO_LIMIT));
    expect(href).toBe('mailto:info@example.org?subject=Sujet');
  });
});

describe('texts', () => {
  it('explains every known action and falls back on the code', () => {
    expect(actionText('dereference').title).toBe('Faire déréférencer la page');
    expect(actionText('something_new')).toEqual({ title: 'something_new', what: '' });
  });

  it('puts the subject above the body', () => {
    expect(letterText('Sujet', 'Texte')).toBe('Objet : Sujet\n\nTexte');
    expect(letterText('', 'Texte')).toBe('Texte');
  });
});

describe('followed requests', () => {
  const request = {
    status: 'sent',
    sent_at: '2026-09-01T10:00:00Z',
    reminded_at: null,
    reminder_at: '2026-10-01T10:00:00Z',
    due: true,
    check: 'still_there',
    checked_at: '2026-10-20T10:00:00Z',
  } as unknown as FollowedRequest;

  it('says where a request stands', () => {
    expect(requestSummary(request)).toBe('Envoyée le 1 septembre 2026 · à relancer');
    expect(requestSummary({ ...request, due: false })).toBe(
      'Envoyée le 1 septembre 2026 · relance possible le 1 octobre 2026',
    );
    expect(requestSummary({ ...request, status: 'waiting', due: false })).toBe(
      'En attente · envoyée le 1 septembre 2026 · relance possible le 1 octobre 2026',
    );
  });

  it('says what the last check saw', () => {
    expect(checkText(request)).toBe('Toujours là au scan du 20 octobre 2026.');
    expect(checkText({ ...request, check: 'gone' })).toMatch(/^Disparue/);
    expect(checkText({ ...request, check: null })).toBeNull();
  });
});
