import { describe, expect, it } from 'vitest';
import { points, reasonEffect, reasonText, riskLevel } from './scores';

describe('riskLevel', () => {
  it.each([
    [0, 'low'],
    [0.24, 'low'],
    [0.25, 'medium'],
    [0.5, 'high'],
    [0.74, 'high'],
    [0.75, 'critical'],
    [1, 'critical'],
  ] as const)('%s is %s', (risk, level) => {
    expect(riskLevel(risk)).toBe(level);
  });
});

describe('reasons', () => {
  it('say what each rule means, with its details', () => {
    expect(reasonText({ code: 'several_sources', points: 15, params: { count: 3 } })).toBe(
      'Trouvée par 3 sources indépendantes.',
    );
    expect(reasonText({ code: 'kind', points: 70, params: { kind: 'address' } })).toBe(
      'Adresse : exposition de base.',
    );
    expect(reasonText({ code: 'sensitive_subdomain', params: { label: 'nas' } })).toContain(
      '« nas »',
    );
  });

  it('fall back to the code for a rule this version does not know', () => {
    expect(reasonText({ code: 'some_new_rule' })).toBe('some_new_rule');
  });

  it('show what a rule did: a value, an addition, a factor', () => {
    expect(reasonEffect({ code: 'sources', points: 60 })).toBe('60');
    expect(reasonEffect({ code: 'corroborated', points: 15 })).toBe('+15');
    expect(reasonEffect({ code: 'something', points: -10 })).toBe('−10');
    expect(reasonEffect({ code: 'weighted', factor: 0.7 })).toBe('×0,7');
    // As the API sends them: the fields a rule doesn't use are null.
    expect(reasonEffect({ code: 'sources', points: 60, factor: null, params: {} })).toBe('60');
    expect(reasonEffect({ code: 'weighted', points: null, factor: 0.85 })).toBe('×0,85');
  });

  it('points are a score out of 100', () => {
    expect(points(0.524)).toBe(52);
    expect(points(1)).toBe(100);
  });
});
