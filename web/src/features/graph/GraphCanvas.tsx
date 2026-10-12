import { layerImage } from '@sigma/node-image';
import { use, useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react';
import Sigma from 'sigma';
import {
  extremityArrow,
  layerFill,
  layerPlain,
  pathLine,
  sdfCircle,
  sdfSquare,
} from 'sigma/rendering';
import { useTheme } from '@/app/theme';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import type { GraphPath } from '@/lib/graph';
import type { GraphData } from '@/lib/types';
import { pictogramsReady } from './kinds';
import { Layout, savePositions, savedPositions } from './layout';
import {
  label as labelOf,
  newGraph,
  recolor,
  sync,
  type EdgeAttributes,
  type NodeAttributes,
  type TraceGraph,
} from './model';

export interface GraphCanvasHandle {
  /** Moves the camera onto a trace. */
  show: (id: number) => void;
  /** The whole graph in view. */
  fit: () => void;
  /** These traces in view (a path). */
  frame: (ids: number[]) => void;
}

interface NodeState {
  isSelected: boolean;
}

type TraceSigma = Sigma<NodeAttributes, EdgeAttributes, Record<string, never>, NodeState>;

const PRIMITIVES = {
  nodes: {
    shapes: [sdfCircle(), sdfSquare()],
    variables: {
      image: { type: 'string' as const, default: '' },
      pictoColor: { type: 'color' as const, default: '#ffffff' },
    },
    layers: [
      layerFill(),
      layerImage({ drawingMode: 'color', colorAttribute: 'pictoColor', padding: 0.24 }),
    ],
  },
  edges: {
    paths: [pathLine()],
    extremities: [extremityArrow()],
    layers: [layerPlain()],
  },
};

// Sigma's style types can't follow these rules through inference: the callbacks say their own.
interface ItemState {
  isHighlighted: boolean;
}
interface StageState {
  hasHighlighted: boolean;
}
const faded = (_a: unknown, state: ItemState, graphState: StageState) =>
  graphState.hasHighlighted && !state.isHighlighted;
const grown = (factor: number) => (a: NodeAttributes) => a.size * factor;

function createSigma(graph: TraceGraph, container: HTMLElement): TraceSigma {
  const options = {
    primitives: PRIMITIVES,
    customNodeState: { isSelected: false },
    settings: {
      renderEdgeLabels: false,
      enableNodeDrag: true,
      hideEdgesOnMove: false,
      labelDensity: 0.4,
      labelRenderedSizeThreshold: 9,
      // Sizes in screen pixels: a node stays readable however large the graph.
      itemSizesReference: 'screen',
    },
    styles: {
      nodes: [
        {
          x: { attribute: 'x' },
          y: { attribute: 'y' },
          size: { attribute: 'size', defaultValue: 6 },
          color: { attribute: 'color' },
          image: { attribute: 'image' },
          pictoColor: { attribute: 'pictoColor' },
          shape: { attribute: 'shape', defaultValue: 'circle' },
          opacity: { attribute: 'opacity', defaultValue: 1 },
          label: { attribute: 'label' },
          labelColor: { attribute: 'labelColor' },
          backdropColor: { attribute: 'backdropColor' },
          backdropShadowColor: 'rgba(0, 0, 0, 0.3)',
          backdropShadowBlur: 8,
          backdropPadding: 4,
          backdropVisibility: 'hidden',
          labelVisibility: 'auto',
          visibility: { whenState: 'isHidden', then: 'hidden', else: 'visible' },
          cursor: 'pointer',
        },
        // Focus: the selected trace and its neighbours stand out, the rest fades.
        { when: faded, then: { opacity: 0.15, labelVisibility: 'hidden' } },
        {
          whenState: 'isHighlighted',
          then: { depth: 'topNodes', labelVisibility: 'visible' },
        },
        {
          whenState: 'isHovered',
          then: {
            size: grown(1.25),
            depth: 'topNodes',
            labelVisibility: 'visible',
            backdropVisibility: 'visible',
          },
        },
        {
          whenState: 'isSelected',
          then: {
            size: grown(1.4),
            depth: 'topNodes',
            labelVisibility: 'visible',
            backdropVisibility: 'visible',
          },
        },
      ],
      edges: [
        {
          size: { attribute: 'size', defaultValue: 1 },
          color: { attribute: 'color' },
          path: 'line',
          head: 'none',
          visibility: { whenState: 'isHidden', then: 'hidden', else: 'visible' },
        },
        { when: faded, then: { opacity: 0.08 } },
        {
          whenState: 'isHighlighted',
          then: { color: { attribute: 'highlight' }, size: 1.6, head: 'arrow', depth: 'topEdges' },
        },
      ],
    },
  };
  return new Sigma(graph, container, options as never) as TraceSigma;
}

/** Turns a state on for what joins the set, off for what leaves it (if it still exists). */
function apply(
  before: ReadonlySet<string>,
  after: ReadonlySet<string>,
  set: (key: string, on: boolean) => void,
  exists: (key: string) => boolean,
) {
  for (const key of before) if (!after.has(key) && exists(key)) set(key, false);
  for (const key of after) if (!before.has(key)) set(key, true);
}

export function GraphCanvas({
  profileId,
  data,
  hidden,
  selected,
  path = null,
  badges,
  onSelect,
  onFold,
  ref,
  label,
}: {
  profileId: number;
  data: GraphData;
  /** Traces the filters leave out. */
  hidden: ReadonlySet<number>;
  selected: number | null;
  /** A path to show instead of the selection's neighbours. */
  path?: GraphPath | null;
  /** How many leaves each folded trace holds ("+3" after its label). */
  badges?: ReadonlyMap<number, number>;
  onSelect: (id: number | null) => void;
  /** A double click folds or unfolds a trace's leaves. */
  onFold?: (id: number) => void;
  ref?: Ref<GraphCanvasHandle>;
  /** What the canvas shows, for assistive technologies. */
  label: string;
}) {
  use(pictogramsReady); // the nodes' pictograms, drawn before the first node
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<TraceGraph>(newGraph());
  const sigma = useRef<TraceSigma | null>(null);
  const layout = useRef<Layout | null>(null);
  const select = useRef(onSelect);
  const fold = useRef(onFold);
  const { resolved: theme } = useTheme();
  const reduced = useReducedMotion();
  const [settling, setSettling] = useState(false);
  useEffect(() => {
    select.current = onSelect;
    fold.current = onFold;
  });

  // The canvas, once.
  useEffect(() => {
    const instance = createSigma(graph.current, container.current!);
    sigma.current = instance;
    layout.current = new Layout(graph.current, () => {
      setSettling(false);
      savePositions(profileId, graph.current);
    });
    instance.on('clickNode', ({ node }) => select.current(Number(node)));
    instance.on('clickStage', () => select.current(null));
    instance.on('doubleClickNode', (event) => {
      if (!fold.current) return;
      event.preventSigmaDefault(); // no zoom: the double click folds
      fold.current(Number(event.node));
    });
    return () => {
      layout.current?.stop();
      instance.kill();
      sigma.current = null;
    };
  }, [profileId]);

  // The data: new traces placed, then the layout settles them.
  const shownHidden = useRef({ nodes: new Set<string>(), edges: new Set<string>() });
  const shownFocus = useRef({ nodes: new Set<string>(), edges: new Set<string>(), selected: '' });
  const first = useRef(true);
  useEffect(() => {
    const saved = first.current ? savedPositions(profileId) : undefined;
    const added = sync(graph.current, data, theme, saved);
    if (!added.length) return;
    // A trace drawn again starts with no state: forget what was set on its previous self.
    for (const key of added) {
      shownHidden.current.nodes.delete(key);
      shownFocus.current.nodes.delete(key);
    }
    if (first.current) {
      first.current = false;
      const known = added.filter((key) => saved?.has(key)).length;
      if (known === added.length) return; // as it was left
      setSettling(true);
      layout.current?.run(known > added.length / 2 ? added : undefined);
      if (!known) sigma.current?.getCamera().setState({ x: 0.5, y: 0.5, ratio: 1 });
    } else if (!reduced) {
      layout.current?.run(added);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the theme recolours below
  }, [data, profileId, reduced]);

  const painted = useRef(theme);
  useEffect(() => {
    if (painted.current === theme) return;
    painted.current = theme;
    recolor(graph.current, theme);
  }, [theme]);

  // Filters, then focus: only the items whose state changes are touched, so that a result
  // arriving live costs little however large the graph.
  useEffect(() => {
    const instance = sigma.current;
    if (!instance) return;
    const g = graph.current;
    const nodes = new Set<string>();
    const edges = new Set<string>();
    for (const id of hidden) {
      const key = String(id);
      if (!g.hasNode(key)) continue;
      nodes.add(key);
      g.forEachEdge(key, (edge) => edges.add(edge));
    }
    const before = shownHidden.current;
    apply(
      before.nodes,
      nodes,
      (key, on) => instance.setNodeState(key, { isHidden: on }),
      g.hasNode.bind(g),
    );
    apply(
      before.edges,
      edges,
      (key, on) => instance.setEdgeState(key, { isHidden: on }),
      g.hasEdge.bind(g),
    );
    shownHidden.current = { nodes, edges };
  }, [hidden, data]);

  // Focus: a path, or the selected trace and its neighbours.
  useEffect(() => {
    const instance = sigma.current;
    if (!instance) return;
    const g = graph.current;
    const key = selected === null ? '' : String(selected);
    const nodes = new Set<string>();
    const edges = new Set<string>();
    if (path) {
      for (const id of path.nodes) if (g.hasNode(String(id))) nodes.add(String(id));
      for (const id of path.edges) if (g.hasEdge(String(id))) edges.add(String(id));
    } else if (key && g.hasNode(key)) {
      nodes.add(key);
      g.forEachNeighbor(key, (n) => nodes.add(n));
      g.forEachEdge(key, (e) => edges.add(e));
    }
    const before = shownFocus.current;
    apply(
      before.nodes,
      nodes,
      (n, on) => instance.setNodeState(n, { isHighlighted: on }),
      g.hasNode.bind(g),
    );
    apply(
      before.edges,
      edges,
      (e, on) => instance.setEdgeState(e, { isHighlighted: on }),
      g.hasEdge.bind(g),
    );
    if (before.selected !== key) {
      if (before.selected && g.hasNode(before.selected)) {
        instance.setNodeState(before.selected, { isSelected: false });
      }
      if (key && g.hasNode(key)) instance.setNodeState(key, { isSelected: true });
    }
    instance.setGraphState({ hasHighlighted: nodes.size > 0 });
    shownFocus.current = { nodes, edges, selected: key };
  }, [selected, path, data]);

  // "+3": the leaves folded into a trace.
  const shownBadges = useRef(new Map<string, number>());
  useEffect(() => {
    const g = graph.current;
    const byId = new Map(data.nodes.map((n) => [String(n.id), n]));
    const next = new Map(
      [...(badges ?? new Map<number, number>())].map(([id, n]) => [String(id), n]),
    );
    for (const key of new Set([...shownBadges.current.keys(), ...next.keys()])) {
      const node = byId.get(key);
      if (!node || !g.hasNode(key) || shownBadges.current.get(key) === next.get(key)) continue;
      const count = next.get(key);
      g.setNodeAttribute(key, 'label', count ? `${labelOf(node)}  +${count}` : labelOf(node));
    }
    shownBadges.current = next;
  }, [badges, data]);

  useImperativeHandle(
    ref,
    () => ({
      show: (id) => {
        const instance = sigma.current;
        const shown = instance?.getNodeDisplayData(String(id));
        if (!instance || !shown) return;
        void instance
          .getCamera()
          .animate({ x: shown.x, y: shown.y, ratio: 0.25 }, { duration: reduced ? 0 : 500 });
      },
      frame: (ids) => {
        const instance = sigma.current;
        if (!instance) return;
        const points = ids
          .map((id) => instance.getNodeDisplayData(String(id)))
          .filter((d) => d !== undefined);
        if (!points.length) return;
        const xs = points.map((p) => p.x);
        const ys = points.map((p) => p.y);
        const [minX, maxX, minY, maxY] = [
          Math.min(...xs),
          Math.max(...xs),
          Math.min(...ys),
          Math.max(...ys),
        ];
        void instance.getCamera().animate(
          {
            x: (minX + maxX) / 2,
            y: (minY + maxY) / 2,
            ratio: Math.min(1, Math.max(0.08, Math.max(maxX - minX, maxY - minY) * 1.4)),
          },
          { duration: reduced ? 0 : 500 },
        );
      },
      fit: () => {
        void sigma.current
          ?.getCamera()
          .animate({ x: 0.5, y: 0.5, ratio: 1, angle: 0 }, { duration: reduced ? 0 : 400 });
      },
    }),
    [reduced],
  );

  return (
    <div className="relative size-full">
      <div
        ref={container}
        role="img"
        aria-label={label}
        className={`size-full ${settling && reduced ? 'invisible' : ''}`}
        data-testid="graph-canvas"
        data-settling={settling || undefined}
      />
      {settling && (
        <p
          role="status"
          className="absolute top-3 left-3 rounded-md bg-background/90 px-2 py-1 text-xs text-muted-foreground shadow-sm"
        >
          Mise en place du graphe…
        </p>
      )}
    </div>
  );
}
