import { describe, expect, it } from 'vitest';
import type { Edge, GraphData, GraphNode } from '@/lib/types';
import { newGraph, sizeFor, sync } from './model';

const node = (id: number, kind: GraphNode['kind'] = 'account'): GraphNode => ({
  id,
  kind,
  display: `trace ${id}`,
  normalized: `trace ${id}`,
  status: 'unreviewed',
  confidence: 0.5,
  risk: 0.2,
  attributes: {},
  first_seen: '2026-01-01T00:00:00Z',
  last_seen: '2026-01-01T00:00:00Z',
  modules: ['github'],
  evidence_count: 1,
});

const edge = (id: number, source: number, target: number, relation = 'has_account'): Edge => ({
  id,
  source_id: source,
  target_id: target,
  relation,
  module: 'github',
  confidence: 0.5,
  first_seen: '2026-01-01T00:00:00Z',
  last_seen: '2026-01-01T00:00:00Z',
});

describe('the graph drawn from the data', () => {
  it('places each trace once, even when two edges join the same two traces', () => {
    const data: GraphData = {
      nodes: [node(1, 'identity'), node(2, 'username'), node(3), node(4, 'url')],
      edges: [
        edge(1, 1, 2, 'declares'),
        edge(2, 2, 3, 'has_account'),
        edge(3, 2, 3, 'links_to'), // the same pair again
        edge(4, 3, 4, 'links_to'),
      ],
      truncated: false,
    };
    const graph = newGraph();
    expect(sync(graph, data, 'light').sort()).toEqual(['1', '2', '3', '4']);
    expect(graph.order).toBe(4);
    expect(graph.size).toBe(4); // both edges between 2 and 3 are drawn
  });

  it('adds what arrives next to what led to it, and drops what is gone', () => {
    const graph = newGraph();
    const first: GraphData = {
      nodes: [node(1, 'identity'), node(2, 'username')],
      edges: [edge(1, 1, 2, 'declares')],
      truncated: false,
    };
    sync(graph, first, 'light');
    const parent = graph.getNodeAttributes('2');
    const added = sync(
      graph,
      { ...first, nodes: [...first.nodes, node(3)], edges: [...first.edges, edge(2, 2, 3)] },
      'light',
    );
    expect(added).toEqual(['3']);
    const child = graph.getNodeAttributes('3');
    expect(Math.hypot(child.x - parent.x, child.y - parent.y)).toBeLessThanOrEqual(12);

    sync(graph, first, 'light');
    expect(graph.hasNode('3')).toBe(false);
  });
});

describe('node sizes', () => {
  it('grow with the risk, the identity biggest, declared traces never tiny', () => {
    expect(sizeFor(0, 'account', false, 100)).toBe(3);
    expect(sizeFor(1, 'address', false, 100)).toBe(14);
    expect(sizeFor(0.5, 'email', false, 100)).toBeGreaterThan(sizeFor(0.2, 'email', false, 100));
    expect(sizeFor(0, 'email', true, 100)).toBe(7);
    expect(sizeFor(0, 'identity', true, 100)).toBe(14);
  });

  it('shrink on large graphs', () => {
    expect(sizeFor(1, 'address', false, 4000)).toBe(7);
  });
});
