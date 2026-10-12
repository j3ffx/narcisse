// A profile's graph as the query cache holds it: live changes, filters and search. Pure
// functions, tested in graph.test.ts.
import type { Edge, EntityStatus, EntityKind, GraphData, GraphNode, Entity, Result } from './types';

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

/**
 * The leaves folded into their trace: traces linked to nothing but it (never the identity nor
 * a declared one). `folded` lists the traces folded, or 'all' for every one. Gives the leaves
 * to hide, and how many each folded trace holds.
 */
export function foldedLeaves(
  data: GraphData,
  folded: ReadonlySet<number> | 'all',
): { hidden: Set<number>; counts: Map<number, number> } {
  const neighbours = new Map<number, Set<number>>();
  const meet = (a: number, b: number) => neighbours.set(a, (neighbours.get(a) ?? new Set()).add(b));
  for (const edge of data.edges) {
    meet(edge.source_id, edge.target_id);
    meet(edge.target_id, edge.source_id);
  }
  const hidden = new Set<number>();
  const counts = new Map<number, number>();
  for (const node of data.nodes) {
    if (node.kind === 'identity' || node.modules.includes('seed')) continue;
    const links = neighbours.get(node.id);
    if (links?.size !== 1) continue;
    const [parent] = links as Set<number>;
    if (folded !== 'all' && !folded.has(parent!)) continue;
    hidden.add(node.id);
    counts.set(parent!, (counts.get(parent!) ?? 0) + 1);
  }
  return { hidden, counts };
}

/** How many leaves each trace has (what folding it would hide). */
export function leafCounts(data: GraphData): Map<number, number> {
  return foldedLeaves(data, 'all').counts;
}

export type Grouping = 'none' | 'kind' | 'source' | 'site';

/** The group a trace falls in, or null when it always stands alone (the identity, declared
 * traces, and for sites, traces without one). */
export function groupKey(node: GraphNode, by: Grouping): string | null {
  if (by === 'none' || node.kind === 'identity' || node.modules.includes('seed')) return null;
  switch (by) {
    case 'kind':
      return node.kind;
    case 'source':
      return node.modules[0] ?? null;
    case 'site': {
      if (node.kind === 'email') return node.display.split('@')[1]?.toLowerCase() ?? null;
      if (node.kind !== 'account' && node.kind !== 'url') return null;
      try {
        return new URL(node.display).hostname.replace(/^www\./, '');
      } catch {
        return null;
      }
    }
  }
}

export interface GraphGroup {
  key: string;
  /** The meta node's id (negative, never a trace's). */
  id: number;
  members: GraphNode[];
}

/**
 * The graph with each group of traces drawn as one node (its id negative), but the groups in
 * `open`, whose traces show again. Edges between groups merge into one. Traces `kept` rejects
 * (filters) are left out. `name` titles a group.
 */
export function grouped(
  data: GraphData,
  by: Grouping,
  open: ReadonlySet<string>,
  kept: (node: GraphNode) => boolean,
  name: (key: string, members: GraphNode[]) => string,
): { data: GraphData; groups: Map<number, GraphGroup> } {
  const members = new Map<string, GraphNode[]>();
  const nodes: GraphNode[] = [];
  for (const node of data.nodes) {
    if (!kept(node)) continue;
    const key = groupKey(node, by);
    if (key === null || open.has(key)) nodes.push(node);
    else members.set(key, [...(members.get(key) ?? []), node]);
  }
  const groups = new Map<number, GraphGroup>();
  const owner = new Map<number, number>();
  [...members.keys()].sort().forEach((key, i) => {
    const list = members.get(key)!;
    if (list.length === 1) {
      nodes.push(list[0]!); // a group of one is the trace itself
      return;
    }
    const id = -(i + 1);
    groups.set(id, { key, id, members: list });
    for (const m of list) owner.set(m.id, id);
    const kinds = new Set(list.map((m) => m.kind));
    nodes.push({
      id,
      kind: kinds.size === 1 ? list[0]!.kind : 'url',
      display: name(key, list),
      normalized: key,
      status: 'unreviewed',
      confidence: null,
      attributes: { group: key, members: list.length },
      first_seen: list.map((m) => m.first_seen).sort()[0]!,
      last_seen: list
        .map((m) => m.last_seen)
        .sort()
        .at(-1)!,
      modules: [...new Set(list.flatMap((m) => m.modules))],
      evidence_count: list.reduce((n, m) => n + m.evidence_count, 0),
    });
  });
  const present = new Set(nodes.map((n) => n.id));
  const edges = new Map<string, Edge>();
  let next = -1;
  for (const edge of data.edges) {
    const source = owner.get(edge.source_id) ?? edge.source_id;
    const target = owner.get(edge.target_id) ?? edge.target_id;
    if (source === target || !present.has(source) || !present.has(target)) continue;
    if (source === edge.source_id && target === edge.target_id) {
      edges.set(String(edge.id), edge);
      continue;
    }
    const key = `${source}>${target}`;
    if (!edges.has(key)) {
      edges.set(key, { ...edge, id: -1_000_000 + next--, source_id: source, target_id: target });
    }
  }
  return { data: { ...data, nodes, edges: [...edges.values()] }, groups };
}
