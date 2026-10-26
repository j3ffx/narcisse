import { describe, expect, it } from 'vitest';
import { MAILTO_LIMIT, actionText, letterText, mailtoHref } from './remediation';

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
