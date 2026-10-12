import { describe, expect, it } from 'vitest';
import { NO_FILTER, passes, search, shortestPath, withEntity, withResult } from './graph';
import type { Edge, GraphData, GraphNode, Result } from './types';

const node = (id: number, display: string, extra: Partial<GraphNode> = {}): GraphNode => ({
  id,
  kind: 'account',
  display,
  normalized: display.toLowerCase(),
  status: 'unreviewed',
  confidence: 0.5,
  attributes: {},
  first_seen: '2026-01-01T00:00:00Z',
  last_seen: '2026-01-01T00:00:00Z',
  modules: ['demo.fake'],
  evidence_count: 1,
  ...extra,
});

const edge = (id: number, source: number, target: number): Edge => ({
  id,
  source_id: source,
  target_id: target,
  relation: 'has_account',
  module: 'demo.fake',
  confidence: 0.5,
  first_seen: '2026-01-01T00:00:00Z',
  last_seen: '2026-01-01T00:00:00Z',
});

const graph: GraphData = {
  nodes: [
    node(1, 'Jeanne Exemple', { kind: 'identity', modules: [] }),
    node(2, 'jeanne', { kind: 'username', modules: ['seed'], confidence: 1 }),
  ],
  edges: [edge(1, 1, 2)],
  truncated: false,
};

const result = (entity: GraphNode, from: number, edgeId: number, module = 'github'): Result => ({
  id: 100 + edgeId,
  profile_id: 1,
  scan_id: 1,
  run_id: 1,
  module,
  entity,
  edge: edge(edgeId, from, entity.id),
  relation: 'has_account',
  confidence: 0.5,
  url: entity.display,
  excerpt: null,
  captured_at: '2026-02-01T00:00:00Z',
});

describe('a loaded graph, live', () => {
  it('takes a new trace and its edge', () => {
    const next = withResult(graph, result(node(3, 'https://github.com/jeanne'), 2, 2), false)!;
    expect(next.nodes.map((n) => n.id)).toEqual([1, 2, 3]);
    expect(next.nodes[2]).toMatchObject({
      modules: ['github'],
      first_seen: '2026-02-01T00:00:00Z',
    });
    expect(next.edges.map((e) => [e.source_id, e.target_id])).toEqual([
      [1, 2],
      [2, 3],
    ]);
  });

  it('counts one more proof of a known trace, once per edge', () => {
    const once = withResult(graph, result(node(2, 'jeanne', { kind: 'username' }), 1, 1), false)!;
    expect(once.nodes[1]).toMatchObject({ evidence_count: 2, modules: ['seed', 'github'] });
    expect(once.edges).toHaveLength(1);
  });

  it('asks to be loaded again when the edge starts from a trace it lacks', () => {
    expect(withResult(graph, result(node(3, 'x'), 99, 2), false)).toBeNull();
  });

  it('leaves out a "not me" trace unless they are shown', () => {
    const notMe = result(node(3, 'x', { status: 'false_positive' }), 2, 2);
    expect(withResult(graph, notMe, false)).toBe(graph);
    expect(withResult(graph, notMe, true)!.nodes).toHaveLength(3);
  });

  it('follows a review, dropping a "not me" trace and its edges', () => {
    const withTrace = withResult(graph, result(node(3, 'x'), 2, 2), false)!;
    const reviewed = withEntity(withTrace, { ...node(3, 'x'), status: 'false_positive' }, false);
    expect(reviewed.nodes.map((n) => n.id)).toEqual([1, 2]);
    expect(reviewed.edges).toHaveLength(1);
    const confirmed = withEntity(withTrace, { ...node(3, 'x'), status: 'confirmed' }, false);
    expect(confirmed.nodes[2]!.status).toBe('confirmed');
  });
});

describe('filters', () => {
  const account = node(3, 'https://github.com/jeanne', {
    confidence: 0.4,
    modules: ['github'],
    last_seen: '2026-03-01T00:00:00Z',
  });

  it('keep what matches each criterion', () => {
    expect(passes(account, NO_FILTER)).toBe(true);
    expect(passes(account, { ...NO_FILTER, kinds: ['email'] })).toBe(false);
    expect(passes(account, { ...NO_FILTER, modules: ['github'] })).toBe(true);
    expect(passes(account, { ...NO_FILTER, statuses: ['confirmed'] })).toBe(false);
    expect(passes(account, { ...NO_FILTER, minConfidence: 0.5 })).toBe(false);
    expect(passes(account, { ...NO_FILTER, since: '2026-02-15' })).toBe(true);
    expect(passes(account, { ...NO_FILTER, since: '2026-03-02' })).toBe(false);
  });

  it('always keep the identity, and declared traces whatever the confidence', () => {
    expect(passes(graph.nodes[0]!, { ...NO_FILTER, kinds: ['email'] })).toBe(true);
    expect(passes(graph.nodes[1]!, { ...NO_FILTER, minConfidence: 0.9 })).toBe(true);
  });
});

describe('search', () => {
  const nodes = [
    node(1, 'https://forum.example.org/u/elodie'),
    node(2, 'Élodie Exemple', { kind: 'name' }),
    node(3, 'elodie'),
  ];

  it('ignores case and accents, and puts the closest first', () => {
    expect(search(nodes, 'ÉLODIE').map((n) => n.id)).toEqual([3, 2, 1]);
    expect(search(nodes, '  ')).toEqual([]);
  });
});

describe('shortest path', () => {
  // 1 → 2 → 3, 1 → 4 → 3, 5 alone; 3 ← 6
  const chain: GraphData = {
    nodes: [1, 2, 3, 4, 5, 6].map((id) => node(id, `n${id}`)),
    edges: [edge(1, 1, 2), edge(2, 2, 3), edge(3, 1, 4), edge(4, 4, 3), edge(5, 6, 3)],
    truncated: false,
  };

  it('follows edges either way, the fewest first', () => {
    expect(shortestPath(chain, 1, 3)).toEqual({ nodes: [1, 2, 3], edges: [1, 2] });
    expect(shortestPath(chain, 6, 1)).toEqual({ nodes: [6, 3, 2, 1], edges: [5, 2, 1] });
    expect(shortestPath(chain, 2, 2)).toEqual({ nodes: [2], edges: [] });
  });

  it('goes round the traces to avoid, or says nothing joins them', () => {
    expect(shortestPath(chain, 1, 3, new Set([2]))).toEqual({ nodes: [1, 4, 3], edges: [3, 4] });
    expect(shortestPath(chain, 1, 5)).toBeNull();
    expect(shortestPath(chain, 1, 3, new Set([3]))).toBeNull();
  });
});
