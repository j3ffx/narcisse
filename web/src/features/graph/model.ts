// The graphology graph the canvas draws, kept in step with the data the API gives.
import Graph from 'graphology';
import type { Edge, GraphData, GraphNode } from '@/lib/types';
import { KIND_COLORS, STAGE_COLORS, pictogram, type Theme } from './kinds';

export interface NodeAttributes {
  x: number;
  y: number;
  size: number;
  label: string;
  kind: GraphNode['kind'];
  color: string;
  image: string;
  pictoColor: string;
  labelColor: string;
  backdropColor: string;
  shape: 'circle' | 'square';
  opacity: number;
  /** Declared by the user (or the identity): drawn square. */
  declared: boolean;
  /** For a group of traces drawn as one node: how many it holds. */
  members: number;
  /** Held in place while the layout settles new traces. */
  fixed?: boolean;
}

export interface EdgeAttributes {
  relation: string;
  size: number;
  color: string;
  highlight: string;
}

export type TraceGraph = Graph<NodeAttributes, EdgeAttributes>;

export const newGraph = (): TraceGraph =>
  new Graph<NodeAttributes, EdgeAttributes>({
    type: 'directed',
    multi: true,
    allowSelfLoops: false,
  });

/** A short label: an address without its scheme, cut when long. */
export function label(node: GraphNode): string {
  const text = node.display.replace(/^https?:\/\/(www\.)?/, '');
  return text.length > 42 ? `${text.slice(0, 40)}…` : text;
}

/** A stable pseudo-random number in [0, 1) for a key: the same node starts at the same place. */
function noise(key: number, salt: number): number {
  const x = Math.sin(key * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** Size by how connected a trace is (its risk will set it once scores exist). */
export function sizeFor(degree: number, kind: GraphNode['kind'], order: number): number {
  // Smaller on large graphs, where nodes would otherwise cover each other.
  const scale = order > 1000 ? Math.max(0.5, Math.sqrt(1000 / order)) : 1;
  if (kind === 'identity') return 14;
  return Math.min(14, (3 + 1.6 * Math.sqrt(degree)) * scale);
}

function nodeLook(node: GraphNode, theme: Theme) {
  const declared = node.kind === 'identity' || node.modules.includes('seed');
  return {
    label: label(node),
    kind: node.kind,
    color: KIND_COLORS[theme][node.kind],
    image: pictogram(node.kind),
    pictoColor: STAGE_COLORS[theme].pictogram,
    labelColor: STAGE_COLORS[theme].label,
    backdropColor: STAGE_COLORS[theme].labelBackdrop,
    shape: declared ? ('square' as const) : ('circle' as const),
    opacity: node.status === 'false_positive' ? 0.35 : 1,
    declared,
    members: typeof node.attributes.members === 'number' ? node.attributes.members : 0,
  };
}

function edgeLook(edge: Edge, theme: Theme): EdgeAttributes {
  return {
    relation: edge.relation,
    size: edge.module === 'seed' ? 1 : 0.6,
    color: STAGE_COLORS[theme].edge,
    highlight: STAGE_COLORS[theme].highlight,
  };
}

/**
 * Brings the graph in step with the data: new traces appear next to the trace they came from
 * (or where they were last time), gone ones leave, changed ones change. Returns the keys of the
 * nodes added, so that the layout can settle them.
 */
export function sync(
  graph: TraceGraph,
  data: GraphData,
  theme: Theme,
  saved: Map<string, [number, number]> = new Map(),
): string[] {
  const wanted = new Set(data.nodes.map((n) => String(n.id)));
  graph.forEachNode((key) => {
    if (!wanted.has(key)) graph.dropNode(key);
  });
  const byId = new Map(data.nodes.map((n) => [String(n.id), n]));
  const children = new Map<string, string[]>();
  for (const edge of data.edges) {
    const source = String(edge.source_id);
    children.set(source, [...(children.get(source) ?? []), String(edge.target_id)]);
  }
  // Breadth first from what is already drawn (or from the roots): each new trace starts out
  // from the one that led to it, the tree fanning outwards, so the layout has little to do.
  const angles = new Map<string, number>();
  const added: string[] = [];
  const place = (key: string, position: [number, number], angle: number) => {
    const node = byId.get(key)!;
    graph.addNode(key, { ...nodeLook(node, theme), x: position[0], y: position[1], size: 4 });
    angles.set(key, angle);
    added.push(key);
  };
  const queue: string[] = [];
  for (const node of data.nodes) {
    const key = String(node.id);
    if (graph.hasNode(key)) {
      graph.mergeNodeAttributes(key, nodeLook(node, theme));
      queue.push(key);
    }
  }
  const targets = new Set(data.edges.map((e) => String(e.target_id)));
  const roots = data.nodes
    .map((n) => String(n.id))
    .filter((k) => !graph.hasNode(k) && !targets.has(k));
  const spread = Math.max(10, Math.sqrt(data.nodes.length) * 10);
  const scatter = (id: number): [number, number] => [
    (noise(id, 2) - 0.5) * spread,
    (noise(id, 3) - 0.5) * spread,
  ];
  for (const key of roots) {
    place(key, saved.get(key) ?? (queue.length ? scatter(Number(key)) : [0, 0]), 0);
    queue.push(key);
  }
  const visit = () => {
    while (queue.length) {
      const parent = queue.shift()!;
      const { x, y } = graph.getNodeAttributes(parent);
      const fresh = (children.get(parent) ?? []).filter((k) => !graph.hasNode(k) && byId.has(k));
      const around = angles.get(parent);
      fresh.forEach((key, i) => {
        // Around the root: the whole circle; further out: the half facing away from it.
        const angle =
          around === undefined || angles.size <= 1
            ? (2 * Math.PI * i) / fresh.length + noise(Number(key), 1)
            : around + ((i + 0.5) / fresh.length - 0.5) * Math.PI;
        const distance = 6 + 6 * noise(Number(key), 4);
        place(
          key,
          saved.get(key) ?? [x + Math.cos(angle) * distance, y + Math.sin(angle) * distance],
          angle,
        );
        queue.push(key);
      });
    }
  };
  visit();
  // Whatever no edge reaches (cut graphs): scattered, then its own descendants.
  for (const node of data.nodes) {
    const key = String(node.id);
    if (graph.hasNode(key)) continue;
    place(key, saved.get(key) ?? scatter(node.id), noise(node.id, 5) * 2 * Math.PI);
    queue.push(key);
    visit();
  }
  const wantedEdges = new Set(data.edges.map((e) => String(e.id)));
  graph.forEachEdge((key) => {
    if (!wantedEdges.has(key)) graph.dropEdge(key);
  });
  for (const edge of data.edges) {
    const key = String(edge.id);
    const source = String(edge.source_id);
    const target = String(edge.target_id);
    if (graph.hasEdge(key) || !graph.hasNode(source) || !graph.hasNode(target)) continue;
    if (source === target) continue;
    graph.addDirectedEdgeWithKey(key, source, target, edgeLook(edge, theme));
  }
  graph.forEachNode((key, attributes) => {
    const size = attributes.members
      ? Math.min(28, 6 + 2 * Math.sqrt(attributes.members))
      : sizeFor(graph.degree(key), attributes.kind, graph.order);
    if (size !== attributes.size) graph.setNodeAttribute(key, 'size', size);
  });
  return added;
}

/**
 * New colours for every node and edge, when the theme changes. One item at a time: sigma can't
 * take a bulk update (`updateEach…`) of items it hasn't drawn yet.
 */
export function recolor(graph: TraceGraph, theme: Theme) {
  graph.forEachNode((key, a) => {
    graph.mergeNodeAttributes(key, {
      color: KIND_COLORS[theme][a.kind],
      pictoColor: STAGE_COLORS[theme].pictogram,
      labelColor: STAGE_COLORS[theme].label,
      backdropColor: STAGE_COLORS[theme].labelBackdrop,
    });
  });
  graph.forEachEdge((key) => {
    graph.mergeEdgeAttributes(key, {
      color: STAGE_COLORS[theme].edge,
      highlight: STAGE_COLORS[theme].highlight,
    });
  });
}
