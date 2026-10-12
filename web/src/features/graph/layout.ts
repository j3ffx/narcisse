// The force-directed layout (ForceAtlas2), computed in a Web Worker so that it never blocks the
// page, and the positions it ends on, kept per profile so that a graph opens where it was left.
import forceAtlas2 from 'graphology-layout-forceatlas2';
import FA2Layout from 'graphology-layout-forceatlas2/worker';
import type { TraceGraph } from './model';

export class Layout {
  private worker: FA2Layout | null = null;
  private timer = 0;

  constructor(
    private readonly graph: TraceGraph,
    private readonly onSettled: () => void,
  ) {}

  get running(): boolean {
    return this.worker?.isRunning() ?? false;
  }

  /**
   * Lays the graph out for a while. With `only`, the other nodes stay where they are: new
   * traces find their place without the rest of the graph jumping.
   */
  run(only?: string[]) {
    this.stop();
    const order = this.graph.order;
    if (order < 2) return;
    if (only) {
      const moving = new Set(only);
      // One node at a time: sigma can't take a bulk update of nodes it hasn't drawn yet.
      this.graph.forEachNode((key) => this.graph.setNodeAttribute(key, 'fixed', !moving.has(key)));
    }
    this.worker = new FA2Layout(this.graph, {
      settings: {
        ...forceAtlas2.inferSettings(this.graph),
        // Room between the clusters: a profile's accounts gather around each username.
        scalingRatio: order > 1000 ? 30 : 10,
        barnesHutOptimize: order > 500,
        adjustSizes: false,
        slowDown: only ? 3 : 1 + Math.log10(order) / 2,
      },
    });
    this.worker.start();
    const duration = only ? 1500 : Math.min(15000, 2000 + order * 2);
    this.timer = window.setTimeout(() => this.settle(), duration);
  }

  private settle() {
    this.stop();
    this.onSettled();
  }

  stop() {
    window.clearTimeout(this.timer);
    if (this.worker) {
      this.worker.kill();
      this.worker = null;
      this.graph.forEachNode((key, a) => {
        if (a.fixed) this.graph.setNodeAttribute(key, 'fixed', false);
      });
    }
  }
}

const storageKey = (profileId: number) => `narcisse.graph.${profileId}.positions`;

/** Where the nodes were when the graph was last laid out (empty if unknown or unreadable). */
export function savedPositions(profileId: number): Map<string, [number, number]> {
  try {
    const raw = localStorage.getItem(storageKey(profileId));
    return new Map(raw ? (JSON.parse(raw) as [string, [number, number]][]) : []);
  } catch {
    return new Map();
  }
}

export function savePositions(profileId: number, graph: TraceGraph) {
  const positions: [string, [number, number]][] = [];
  graph.forEachNode((key, { x, y }) => {
    positions.push([key, [Math.round(x * 100) / 100, Math.round(y * 100) / 100]]);
  });
  try {
    localStorage.setItem(storageKey(profileId), JSON.stringify(positions));
  } catch {
    // Storage full or blocked: the graph will be laid out again next time.
  }
}
