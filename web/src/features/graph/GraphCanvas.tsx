import { layerImage } from '@sigma/node-image';
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react';
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
import type { GraphData } from '@/lib/types';
import { Layout, savePositions, savedPositions } from './layout';
import {
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

export function GraphCanvas({
  profileId,
  data,
  hidden,
  selected,
  onSelect,
  ref,
  label,
}: {
  profileId: number;
  data: GraphData;
  /** Traces the filters leave out. */
  hidden: ReadonlySet<number>;
  selected: number | null;
  onSelect: (id: number | null) => void;
  ref?: Ref<GraphCanvasHandle>;
  /** What the canvas shows, for assistive technologies. */
  label: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<TraceGraph>(newGraph());
  const sigma = useRef<TraceSigma | null>(null);
  const layout = useRef<Layout | null>(null);
  const select = useRef(onSelect);
  const { resolved: theme } = useTheme();
  const reduced = useReducedMotion();
  const [settling, setSettling] = useState(false);
  useEffect(() => {
    select.current = onSelect;
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
    return () => {
      layout.current?.stop();
      instance.kill();
      sigma.current = null;
    };
  }, [profileId]);

  // The data: new traces placed, then the layout settles them.
  const first = useRef(true);
  useEffect(() => {
    const saved = first.current ? savedPositions(profileId) : undefined;
    const added = sync(graph.current, data, theme, saved);
    if (!added.length) return;
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

  // Filters.
  useEffect(() => {
    const instance = sigma.current;
    if (!instance) return;
    const g = graph.current;
    g.forEachNode((key) => instance.setNodeState(key, { isHidden: hidden.has(Number(key)) }));
    g.forEachEdge((key, _a, source, target) =>
      instance.setEdgeState(key, {
        isHidden: hidden.has(Number(source)) || hidden.has(Number(target)),
      }),
    );
  }, [hidden, data]);

  // Selection: the trace and its neighbours in focus.
  useEffect(() => {
    const instance = sigma.current;
    if (!instance) return;
    const g = graph.current;
    const key = selected === null ? null : String(selected);
    const focus = new Set<string>();
    if (key && g.hasNode(key)) {
      focus.add(key);
      g.forEachNeighbor(key, (n) => focus.add(n));
    }
    g.forEachNode((n) =>
      instance.setNodeState(n, { isHighlighted: focus.has(n), isSelected: n === key }),
    );
    g.forEachEdge((e, _a, source, target) =>
      instance.setEdgeState(e, {
        isHighlighted: key !== null && (source === key || target === key),
      }),
    );
    instance.setGraphState({ hasHighlighted: focus.size > 0 });
  }, [selected, data]);

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
