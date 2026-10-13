import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import {
  foldedLeaves,
  grouped,
  isFiltering,
  leafCounts,
  type GraphGroup,
  type GraphPath,
  type GraphViewState,
  type Grouping,
} from '@/lib/graph';
import { KIND_LABELS } from '@/lib/labels';
import { useGraph } from '@/lib/queries';
import type { EntityKind, GraphData, GraphNode } from '@/lib/types';
import { useTheme } from '@/app/theme';
import { cn } from 'cn';
import { MaximizeIcon, ShrinkIcon } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { GraphCanvas, type GraphCanvasHandle } from './GraphCanvas';
import { KIND_COLORS, KIND_ICONS } from './kinds';
import { TraceFilters } from './TraceFilters';
import { GroupPanel } from './GroupPanel';
import { PathFinder } from './PathFinder';
import { SavedViews } from './SavedViews';
import { TracePanel } from './TracePanel';
import { TraceSearch } from './TraceSearch';
import { useHidden, useSelectedTrace, useSourceTitle, type TraceView } from './useTraceView';

/** The toolbar both views share: search, filters, "not me" traces, and what is shown. */
export function TraceToolbar({
  data,
  view,
  hidden,
  onPick,
  children,
}: {
  data: GraphData;
  view: TraceView;
  hidden: ReadonlySet<number>;
  onPick: (id: number) => void;
  children?: ReactNode;
}) {
  const sourceTitle = useSourceTitle();
  const shown = data.nodes.length - hidden.size;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <TraceSearch nodes={data.nodes} onPick={(node) => onPick(node.id)} />
      <TraceFilters
        nodes={data.nodes}
        filter={view.filter}
        onChange={view.setFilter}
        sourceTitle={sourceTitle}
      />
      <Label className="flex items-center gap-2 font-normal">
        <Checkbox
          checked={view.falsePositives}
          onCheckedChange={(c) => view.setFalsePositives(c === true)}
        />
        Afficher les « pas moi »
      </Label>
      {children}
      <p className="ml-auto text-sm text-muted-foreground" role="status" data-testid="trace-count">
        {isFiltering(view.filter)
          ? `${shown} trace${shown > 1 ? 's' : ''} sur ${data.nodes.length}`
          : `${data.nodes.length} trace${data.nodes.length > 1 ? 's' : ''}`}
      </p>
    </div>
  );
}

const GROUPINGS: [Grouping, string][] = [
  ['none', 'Aucun'],
  ['kind', 'Par type'],
  ['source', 'Par source'],
  ['site', 'Par site'],
];

export function GraphView({ profileId, view }: { profileId: number; view: TraceView }) {
  const graph = useGraph(profileId, view.falsePositives);
  const [selected, select] = useSelectedTrace();
  const hidden = useHidden(graph.data, view.filter);
  const canvas = useRef<GraphCanvasHandle>(null);
  const sourceTitle = useSourceTitle();

  // Groups: each drawn as one node, but those opened.
  const [grouping, setGrouping] = useState<Grouping>('none');
  const [opened, setOpened] = useState<ReadonlySet<string>>(new Set());
  const groupName = useCallback(
    (key: string, members: GraphNode[]) => {
      const title =
        grouping === 'kind'
          ? KIND_LABELS[key as EntityKind]
          : grouping === 'source'
            ? sourceTitle(key)
            : key;
      return `${title} · ${members.length}`;
    },
    [grouping, sourceTitle],
  );
  const drawn = useMemo(() => {
    if (!graph.data || grouping === 'none') {
      return { data: graph.data, groups: new Map<number, GraphGroup>(), hidden };
    }
    const result = grouped(graph.data, grouping, opened, (n) => !hidden.has(n.id), groupName);
    return { ...result, hidden: NOTHING };
  }, [graph.data, grouping, opened, hidden, groupName]);

  // A path holds while its first trace stays selected.
  const [linked, setLinked] = useState<{ from: number; path: GraphPath } | null>(null);
  const path = linked && linked.from === selected ? linked.path : null;

  // Folded leaves: of some traces, or of all at once.
  const [folded, setFolded] = useState<ReadonlySet<number>>(new Set());
  const [foldAll, setFoldAll] = useState(false);
  const fold = useMemo(
    () => (drawn.data ? foldedLeaves(drawn.data, foldAll ? 'all' : folded) : null),
    [drawn.data, folded, foldAll],
  );
  const leaves = useMemo(
    () => (drawn.data ? leafCounts(drawn.data) : new Map<number, number>()),
    [drawn.data],
  );
  const shown = useMemo(
    () => (fold?.hidden.size ? new Set([...drawn.hidden, ...fold.hidden]) : drawn.hidden),
    [drawn.hidden, fold],
  );
  const toggleFold = (id: number) => {
    if (!leaves.get(id)) return;
    setFoldAll(false);
    const base = foldAll ? new Set(leaves.keys()) : new Set(folded);
    if (base.has(id)) base.delete(id);
    else base.add(id);
    setFolded(base);
  };
  const isFolded = (id: number) => foldAll || folded.has(id);

  // Arriving with a trace selected (from the list, a link): the camera goes to it once drawn.
  const arrived = useRef(false);
  useEffect(() => {
    if (arrived.current || !graph.isSuccess) return;
    arrived.current = true;
    if (selected === null) return;
    const timer = window.setTimeout(() => canvas.current?.show(selected), 300);
    return () => window.clearTimeout(timer);
  }, [graph.isSuccess, selected]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !(event.target as HTMLElement).closest('input, [role=dialog]'))
        select(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [select]);

  if (graph.isPending) return <Pending label="Chargement du graphe…" />;
  if (graph.isError || !drawn.data) return <p role="alert">{errorMessage(graph.error)}</p>;
  const all = graph.data;
  const data = drawn.data;
  const groupOf = (id: number) =>
    [...drawn.groups.values()].find((g) => g.members.some((m) => m.id === id));
  const show = (id: number) => {
    const group = groupOf(id);
    select(id);
    if (!group) {
      canvas.current?.show(id);
      return;
    }
    // In a closed group: open it, then go to the trace once it is drawn.
    setOpened(new Set([...opened, group.key]));
    window.setTimeout(() => canvas.current?.show(id), 150);
  };
  const openGroup = (id: number) => {
    const group = drawn.groups.get(id);
    if (!group) return false;
    setOpened(new Set([...opened, group.key]));
    select(null);
    return true;
  };
  const group = selected !== null ? drawn.groups.get(selected) : undefined;

  // Saved views: everything above, and the camera.
  const viewState = (): GraphViewState => ({
    filter: view.filter,
    falsePositives: view.falsePositives,
    grouping,
    opened: [...opened],
    folded: [...folded],
    foldAll,
    selected,
    camera: canvas.current?.camera() ?? null,
  });
  const applyView = (state: GraphViewState) => {
    view.setFilter(state.filter);
    view.setFalsePositives(state.falsePositives);
    setGrouping(state.grouping);
    setOpened(new Set(state.opened));
    setFolded(new Set(state.folded));
    setFoldAll(state.foldAll);
    select(state.selected);
    // Once the graph is drawn as the view had it.
    if (state.camera) {
      const camera = state.camera;
      window.setTimeout(() => canvas.current?.setCamera(camera), 300);
    }
  };

  return (
    <div className="grid gap-3">
      <TraceToolbar data={all} view={view} hidden={hidden} onPick={show}>
        <Label className="flex items-center gap-2 font-normal">
          Regrouper
          <select
            className="h-8 rounded-lg border bg-background px-2 text-sm"
            value={grouping}
            onChange={(e) => {
              setGrouping(e.target.value as Grouping);
              setOpened(new Set());
              select(null);
            }}
          >
            {GROUPINGS.map(([value, title]) => (
              <option key={value} value={value}>
                {title}
              </option>
            ))}
          </select>
        </Label>
        <Button
          variant={foldAll ? 'secondary' : 'ghost'}
          aria-pressed={foldAll}
          onClick={() => {
            setFoldAll(!foldAll);
            setFolded(new Set());
          }}
        >
          <ShrinkIcon aria-hidden />
          Replier les feuilles
        </Button>
        <Button variant="ghost" onClick={() => canvas.current?.fit()}>
          <MaximizeIcon aria-hidden />
          Tout voir
        </Button>
        <SavedViews profileId={profileId} current={viewState} onApply={applyView} />
      </TraceToolbar>
      {all.truncated && (
        <p className="text-sm text-muted-foreground">
          Trop de traces pour toutes les dessiner : les plus récemment vues sont affichées.
        </p>
      )}
      <div
        className={cn(
          'grid h-[calc(100dvh-14rem)] min-h-[28rem] gap-3',
          selected !== null && 'lg:grid-cols-[minmax(0,1fr)_24rem]',
        )}
      >
        <div className="relative min-h-[24rem] overflow-hidden rounded-lg border bg-card">
          {all.nodes.length <= 1 ? (
            <p className="p-6 text-sm text-muted-foreground">
              Rien à relier pour l’instant : lance un scan, les traces apparaîtront ici au fil de
              l’eau.
            </p>
          ) : (
            <GraphCanvas
              ref={canvas}
              profileId={profileId}
              data={data}
              hidden={shown}
              selected={selected}
              path={path}
              badges={fold?.counts}
              onSelect={select}
              onFold={(id) => {
                if (!openGroup(id)) toggleFold(id);
              }}
              label={`Graphe de ${all.nodes.length} traces. La vue Liste en donne le même contenu.`}
            />
          )}
          <Legend nodes={all.nodes.map((n) => n.kind)} />
        </div>
        {group && (
          <GroupPanel
            key={group.id}
            group={group}
            title={data.nodes.find((n) => n.id === group.id)?.display ?? group.key}
            onOpen={() => openGroup(group.id)}
            onPick={show}
            onClose={() => select(null)}
          />
        )}
        {selected !== null && selected >= 0 && (
          <TracePanel
            profileId={profileId}
            key={selected}
            id={selected}
            onSelect={show}
            onClose={() => select(null)}
            sourceTitle={sourceTitle}
            extra={
              <>
                {(leaves.get(selected) ?? 0) > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-fit"
                    aria-pressed={isFolded(selected)}
                    onClick={() => toggleFold(selected)}
                  >
                    {isFolded(selected) ? 'Déplier' : 'Replier'} ses {leaves.get(selected)} trace
                    {(leaves.get(selected) ?? 0) > 1 ? 's' : ''} isolée
                    {(leaves.get(selected) ?? 0) > 1 ? 's' : ''}
                  </Button>
                )}
                <PathFinder
                  data={data}
                  from={selected}
                  hidden={drawn.hidden}
                  path={path}
                  onPath={(found) => {
                    setLinked(found ? { from: selected, path: found } : null);
                    if (found) canvas.current?.frame(found.nodes);
                  }}
                  onShow={(id) => canvas.current?.show(id)}
                />
              </>
            }
          />
        )}
      </div>
    </div>
  );
}

const NOTHING: ReadonlySet<number> = new Set();

function Legend({ nodes }: { nodes: EntityKind[] }) {
  const { resolved } = useTheme();
  const kinds = useMemo(() => [...new Set(nodes)], [nodes]);
  return (
    <ul
      aria-label="Légende"
      className="absolute bottom-2 left-2 flex max-w-[calc(100%-1rem)] sm:max-w-[calc(100%-12rem)] flex-wrap gap-x-3 gap-y-1 rounded-md bg-background/85 px-2 py-1 text-xs"
    >
      {kinds.map((kind) => {
        const Icon = KIND_ICONS[kind];
        return (
          <li key={kind} className="flex items-center gap-1">
            <span
              className="flex size-4 items-center justify-center rounded-full"
              style={{ backgroundColor: KIND_COLORS[resolved][kind] }}
            >
              <Icon aria-hidden className="size-2.5 text-background" strokeWidth={3} />
            </span>
            {KIND_LABELS[kind]}
          </li>
        );
      })}
    </ul>
  );
}
