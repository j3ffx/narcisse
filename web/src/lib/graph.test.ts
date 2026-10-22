import { describe, expect, it } from 'vitest';
import {
  NO_FILTER,
  foldedLeaves,
  groupKey,
  grouped,
  passes,
  readViewState,
  search,
  shortestPath,
  withEntity,
  withResult,
} from './graph';
import type { Edge, GraphData, GraphNode, Result } from './types';

const node = (id: number, display: string, extra: Partial<GraphNode> = {}): GraphNode => ({
  id,
  kind: 'account',
  display,
  normalized: display.toLowerCase(),
  status: 'unreviewed',
  confidence: 0.5,
  risk: 0.2,
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

  it('follows a trace whose scores changed (a neighbour was reviewed)', () => {
    const withTrace = withResult(graph, result(node(3, 'x'), 2, 2), false)!;
    const doubted = withEntity(withTrace, { ...node(3, 'x'), confidence: 0.15, risk: 0.1 }, false);
    expect(doubted.nodes[2]).toMatchObject({ confidence: 0.15, risk: 0.1 });
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
    expect(passes(account, { ...NO_FILTER, minRisk: 0.25 })).toBe(false); // its risk is 0.2
    expect(passes({ ...account, risk: 0.6 }, { ...NO_FILTER, minRisk: 0.5 })).toBe(true);
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

describe('folded leaves', () => {
  // identity 1 → seed 2 → account 3 → site 4, site 5; account 3 → name 6 ← account 7 ← seed 2
  const tree: GraphData = {
    nodes: [
      node(1, 'Jeanne', { kind: 'identity', modules: [] }),
      node(2, 'jeanne', { kind: 'username', modules: ['seed'] }),
      node(3, 'a'),
      node(4, 'site 4', { kind: 'url' }),
      node(5, 'site 5', { kind: 'url' }),
      node(6, 'Jeanne E.', { kind: 'name' }),
      node(7, 'b'),
    ],
    edges: [
      edge(1, 1, 2),
      edge(2, 2, 3),
      edge(3, 3, 4),
      edge(4, 3, 5),
      edge(5, 3, 6),
      edge(6, 7, 6),
      edge(7, 2, 7),
    ],
    truncated: false,
  };

  it('hides what hangs from a folded trace only', () => {
    const { hidden, counts } = foldedLeaves(tree, new Set([3]));
    expect([...hidden]).toEqual([4, 5]); // 6 also hangs from 7
    expect(counts.get(3)).toBe(2);
  });

  it('folds every trace at once, never a declared one', () => {
    expect([...foldedLeaves(tree, 'all').hidden]).toEqual([4, 5]);
    expect(foldedLeaves(tree, new Set([1])).hidden.size).toBe(0); // the seed stays
  });
});

describe('groups', () => {
  const data: GraphData = {
    nodes: [
      node(1, 'Jeanne', { kind: 'identity', modules: [] }),
      node(2, 'jeanne', { kind: 'username', modules: ['seed'] }),
      node(3, 'https://github.com/jeanne', { modules: ['github'] }),
      node(4, 'https://www.github.com/jeanne2', { modules: ['github'] }),
      node(5, 'https://gitlab.com/jeanne', { modules: ['gitlab'] }),
      node(6, 'jeanne@example.org', { kind: 'email', modules: ['github'] }),
    ],
    edges: [
      edge(1, 1, 2),
      edge(2, 2, 3),
      edge(3, 2, 4),
      edge(4, 2, 5),
      edge(5, 3, 6),
      edge(6, 4, 6),
    ],
    truncated: false,
  };
  const name = (key: string, members: GraphNode[]) => `${key} · ${members.length}`;

  it('draws each group as one node, and merges the edges that meet there', () => {
    const { data: view, groups } = grouped(data, 'source', new Set(), () => true, name);
    // github: 3, 4, 6; gitlab: 5 alone stays itself
    expect(view.nodes.map((n) => n.display).sort()).toEqual([
      'Jeanne',
      'github · 3',
      'https://gitlab.com/jeanne',
      'jeanne',
    ]);
    const github = [...groups.values()].find((g) => g.key === 'github')!;
    expect(github.members.map((m) => m.id)).toEqual([3, 4, 6]);
    const toGroup = view.edges.filter((e) => e.target_id === github.id);
    expect(toGroup).toHaveLength(1); // 2 → 3 and 2 → 4 merged; 3 → 6, 4 → 6 inside
    expect(view.edges).toHaveLength(3);
  });

  it('gives a group the risk of its most exposing trace', () => {
    const risky = { ...data, nodes: data.nodes.map((n) => (n.id === 4 ? { ...n, risk: 0.8 } : n)) };
    const { data: view, groups } = grouped(risky, 'source', new Set(), () => true, name);
    const github = [...groups.values()].find((g) => g.key === 'github')!;
    expect(view.nodes.find((n) => n.id === github.id)!.risk).toBe(0.8);
  });

  it('opens a group, groups by site, and leaves out what the filters reject', () => {
    const open = grouped(data, 'source', new Set(['github']), () => true, name);
    expect(open.groups.size).toBe(0);
    expect(open.data.nodes).toHaveLength(6);

    expect(groupKey(data.nodes[3]!, 'site')).toBe('github.com');
    expect(groupKey(data.nodes[5]!, 'site')).toBe('example.org');
    expect(groupKey(data.nodes[1]!, 'site')).toBeNull(); // declared
    const bySite = grouped(data, 'site', new Set(), (n) => n.id !== 6, name);
    expect(bySite.data.nodes.map((n) => n.display)).toContain('github.com · 2');
    expect(bySite.data.nodes.some((n) => n.id === 6)).toBe(false);
  });
});

describe('saved view state', () => {
  it('keeps what fits and defaults the rest', () => {
    const state = readViewState({
      filter: {
        kinds: ['email', 'robot'],
        minConfidence: 0.5,
        minRisk: 'high',
        since: '2026-01-01',
        statuses: 3,
      },
      grouping: 'site',
      opened: ['github.com', 4],
      folded: [12, 'x'],
      camera: { x: 0.4, y: 0.6, ratio: 0.3 },
      selected: 7,
    });
    expect(state).toEqual({
      filter: { ...NO_FILTER, kinds: ['email'], minConfidence: 0.5, since: '2026-01-01' },
      falsePositives: false,
      grouping: 'site',
      opened: ['github.com'],
      folded: [12],
      foldAll: false,
      selected: 7,
      camera: { x: 0.4, y: 0.6, ratio: 0.3, angle: 0 },
    });
    expect(readViewState('nonsense')).toMatchObject({ filter: NO_FILTER, grouping: 'none' });
  });
});
