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
import type { CameraState, GraphPath } from '@/lib/graph';
import type { GraphData } from '@/lib/types';
import { STAGE_COLORS, pictogramsReady } from './kinds';
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
  /** Where the camera is, and putting it back there (saved views). */
  camera: () => CameraState | null;
  setCamera: (state: CameraState) => void;
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

// The minimap: the whole graph, small, with the frame of what the canvas shows. Positions are
// sigma's framed coordinates (the camera's own), fitted into the minimap.
const MINI = { width: 168, height: 112, margin: 6 };

interface MiniFit {
  scale: number;
  x0: number;
  y0: number;
  /** -1 when the screen's y runs against the graph's. */
  flip: number;
}

function miniFit(instance: TraceSigma, graph: TraceGraph): MiniFit | null {
  let [minX, maxX, minY, maxY] = [Infinity, -Infinity, Infinity, -Infinity];
  graph.forEachNode((key) => {
    const shown = instance.getNodeDisplayData(key);
    if (!shown) return;
    minX = Math.min(minX, shown.x);
    maxX = Math.max(maxX, shown.x);
    minY = Math.min(minY, shown.y);
    maxY = Math.max(maxY, shown.y);
  });
  if (minX === Infinity) return null;
  const inner = { w: MINI.width - 2 * MINI.margin, h: MINI.height - 2 * MINI.margin };
  const scale = Math.min(inner.w / (maxX - minX || 1), inner.h / (maxY - minY || 1));
  const top = instance.framedGraphToViewport({ x: 0, y: 0 }).y;
  const below = instance.framedGraphToViewport({ x: 0, y: 1 }).y;
  const flip = below < top ? -1 : 1;
  return {
    scale,
    x0: (minX + maxX) / 2,
    y0: (minY + maxY) / 2,
    flip,
  };
}

const toMini = (fit: MiniFit, x: number, y: number) => ({
  x: MINI.width / 2 + (x - fit.x0) * fit.scale,
  y: MINI.height / 2 + fit.flip * (y - fit.y0) * fit.scale,
});

const fromMini = (fit: MiniFit, x: number, y: number) => ({
  x: fit.x0 + (x - MINI.width / 2) / fit.scale,
  y: fit.y0 + (fit.flip * (y - MINI.height / 2)) / fit.scale,
});

function drawMinimap(
  instance: TraceSigma,
  graph: TraceGraph,
  canvas: HTMLCanvasElement,
  frame: string,
): MiniFit | null {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = MINI.width * ratio;
  canvas.height = MINI.height * ratio;
  const ctx = canvas.getContext('2d');
  const fit = miniFit(instance, graph);
  if (!ctx || !fit) return fit;
  ctx.scale(ratio, ratio);
  graph.forEachNode((key, a) => {
    const shown = instance.getNodeDisplayData(key);
    if (!shown || instance.getNodeState(key).isHidden) return;
    const p = toMini(fit, shown.x, shown.y);
    ctx.fillStyle = a.color;
    ctx.fillRect(p.x - 1, p.y - 1, 2, 2);
  });
  const { width, height } = instance.getDimensions();
  const corner = (x: number, y: number) => {
    const at = instance.viewportToFramedGraph({ x, y });
    return toMini(fit, at.x, at.y);
  };
  const a = corner(0, 0);
  const b = corner(width, height);
  ctx.strokeStyle = frame;
  ctx.lineWidth = 1.5;
  ctx.strokeRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y));
  return fit;
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
  const mini = useRef<HTMLCanvasElement>(null);
  const miniFitRef = useRef<MiniFit | null>(null);
  const frameColor = useRef('');
  const graph = useRef<TraceGraph>(newGraph());
  const sigma = useRef<TraceSigma | null>(null);
  const layout = useRef<Layout | null>(null);
  const select = useRef(onSelect);
  const fold = useRef(onFold);
  const { resolved: theme } = useTheme();
  const reduced = useReducedMotion();
  const [settling, setSettling] = useState(false);
  useEffect(() => {
    frameColor.current = STAGE_COLORS[theme].highlight;
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
    // The minimap follows the canvas, at most a few times a second.
    let pending = 0;
    let drawn = 0;
    instance.on('afterRender', () => {
      if (pending || !mini.current) return;
      pending = window.setTimeout(
        () => {
          pending = 0;
          drawn = performance.now();
          if (mini.current) {
            miniFitRef.current = drawMinimap(
              instance,
              graph.current,
              mini.current,
              frameColor.current,
            );
          }
        },
        Math.max(0, 200 - (performance.now() - drawn)),
      );
    });
    return () => {
      window.clearTimeout(pending);
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
    // What is drawn, for tests and measures (no re-render: straight on the element).
    container.current!.dataset.nodes = String(graph.current.order);
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
    container.current!.dataset.visible = String(g.order - nodes.size);
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

  // A point of the minimap, clicked or dragged over: the camera goes there.
  const moveTo = (x: number, y: number) => {
    const instance = sigma.current;
    const fit = miniFitRef.current;
    if (!instance || !fit) return;
    instance.getCamera().setState(fromMini(fit, x, y));
  };

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
      camera: () => {
        const state = sigma.current?.getCamera().getState();
        return state ? { x: state.x, y: state.y, ratio: state.ratio, angle: state.angle } : null;
      },
      setCamera: (state) => {
        void sigma.current?.getCamera().animate(state, { duration: reduced ? 0 : 400 });
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
      <canvas
        ref={mini}
        aria-hidden
        className="absolute right-2 bottom-2 hidden cursor-crosshair rounded-md border bg-background/85 sm:block"
        style={{ width: MINI.width, height: MINI.height }}
        data-testid="minimap"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          moveTo(e.nativeEvent.offsetX, e.nativeEvent.offsetY);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) moveTo(e.nativeEvent.offsetX, e.nativeEvent.offsetY);
        }}
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
