// A profile's graph as the query cache holds it: live changes, filters and search. Pure
// functions, tested in graph.test.ts.
import type { EntityStatus, EntityKind, GraphData, GraphNode, Entity, Result } from './types';

/**
 * A new result in a loaded graph: its trace (new, or one more proof of a known one) and its
 * edge. `null` when the graph can't take it as it is (the edge starts from a trace it doesn't
 * hold yet, such as a seed added since): it must be loaded again.
 */
export function withResult(
  data: GraphData,
  result: Result,
  falsePositives: boolean,
): GraphData | null {
  const { entity, edge } = result;
  if (!falsePositives && entity.status === 'false_positive') return data;
  const ids = new Set(data.nodes.map((n) => n.id));
  if (edge && !ids.has(edge.source_id)) return null;
  const known = ids.has(entity.id);
  const nodes = known
    ? data.nodes.map((n) =>
        n.id === entity.id
          ? {
              ...n,
              ...entity,
              last_seen: result.captured_at,
              modules: n.modules.includes(result.module)
                ? n.modules
                : [...n.modules, result.module],
              evidence_count: n.evidence_count + 1,
            }
          : n,
      )
    : [
        ...data.nodes,
        {
          ...entity,
          first_seen: result.captured_at,
          last_seen: result.captured_at,
          modules: [result.module],
          evidence_count: 1,
        },
      ];
  const edges =
    edge && !data.edges.some((e) => e.id === edge.id) ? [...data.edges, edge] : data.edges;
  return { ...data, nodes, edges };
}

/** A reviewed trace: its new status, or its leaving when "not me" traces are hidden. */
export function withEntity(data: GraphData, entity: Entity, falsePositives: boolean): GraphData {
  if (!data.nodes.some((n) => n.id === entity.id)) return data;
  if (!falsePositives && entity.status === 'false_positive') {
    return {
      ...data,
      nodes: data.nodes.filter((n) => n.id !== entity.id),
      edges: data.edges.filter((e) => e.source_id !== entity.id && e.target_id !== entity.id),
    };
  }
  return {
    ...data,
    nodes: data.nodes.map((n) => (n.id === entity.id ? { ...n, status: entity.status } : n)),
  };
}

export interface TraceFilter {
  /** Kinds shown; empty: every kind. */
  kinds: EntityKind[];
  /** Sources shown; empty: every source. */
  modules: string[];
  /** Statuses shown; empty: every status. */
  statuses: EntityStatus[];
  /** Only traces at least this sure (0: all). Declared ones always pass. */
  minConfidence: number;
  /** Only traces seen since this day (ISO date), or null. */
  since: string | null;
}

export const NO_FILTER: TraceFilter = {
  kinds: [],
  modules: [],
  statuses: [],
  minConfidence: 0,
  since: null,
};

export function isFiltering(filter: TraceFilter): boolean {
  return (
    filter.kinds.length > 0 ||
    filter.modules.length > 0 ||
    filter.statuses.length > 0 ||
    filter.minConfidence > 0 ||
    filter.since !== null
  );
}

/** Whether a trace passes the filter. The identity always does: everything hangs from it. */
export function passes(node: GraphNode, filter: TraceFilter): boolean {
  if (node.kind === 'identity') return true;
  if (filter.kinds.length && !filter.kinds.includes(node.kind)) return false;
  if (filter.statuses.length && !filter.statuses.includes(node.status)) return false;
  if (filter.modules.length && !node.modules.some((m) => filter.modules.includes(m))) return false;
  const declared = node.modules.includes('seed');
  if (!declared && filter.minConfidence > 0 && (node.confidence ?? 0) < filter.minConfidence) {
    return false;
  }
  if (filter.since && node.last_seen.slice(0, 10) < filter.since) return false;
  return true;
}

/** Folds case and accents: « Élodie » finds « elodie ». */
export function fold(text: string): string {
  return text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
}

/** The traces whose text contains the query, the closest first (starts with it, then shorter). */
export function search(nodes: GraphNode[], query: string, limit = 20): GraphNode[] {
  const q = fold(query.trim());
  if (!q) return [];
  return nodes
    .map((node) => ({ node, text: fold(node.display) }))
    .filter(({ text }) => text.includes(q))
    .sort(
      (a, b) =>
        Number(!a.text.startsWith(q)) - Number(!b.text.startsWith(q)) ||
        a.text.length - b.text.length,
    )
    .slice(0, limit)
    .map(({ node }) => node);
}

export interface GraphPath {
  /** Trace ids, from the first to the last. */
  nodes: number[];
  /** Edge ids, between consecutive traces. */
  edges: number[];
}

/**
 * The shortest way from one trace to another, whatever the edges' direction ("how is this
 * account related to my e-mail?"), avoiding the traces in `avoid` (those the filters hide).
 * Null when nothing joins them.
 */
export function shortestPath(
  data: GraphData,
  from: number,
  to: number,
  avoid: ReadonlySet<number> = new Set(),
): GraphPath | null {
  if (avoid.has(from) || avoid.has(to)) return null;
  const links = new Map<number, [number, number][]>();
  const link = (a: number, b: number, edge: number) =>
    links.set(a, [...(links.get(a) ?? []), [b, edge]]);
  for (const edge of data.edges) {
    if (avoid.has(edge.source_id) || avoid.has(edge.target_id)) continue;
    link(edge.source_id, edge.target_id, edge.id);
    link(edge.target_id, edge.source_id, edge.id);
  }
  const came = new Map<number, [number, number] | null>([[from, null]]);
  const queue = [from];
  for (let i = 0; i < queue.length && !came.has(to); i++) {
    const node = queue[i]!;
    for (const [next, edge] of links.get(node) ?? []) {
      if (came.has(next)) continue;
      came.set(next, [node, edge]);
      queue.push(next);
    }
  }
  if (!came.has(to)) return null;
  const nodes = [to];
  const edges: number[] = [];
  for (let step = came.get(to); step; step = came.get(step[0])) {
    nodes.unshift(step[0]);
    edges.unshift(step[1]);
  }
  return { nodes, edges };
}
