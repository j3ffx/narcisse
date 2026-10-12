import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { isFiltering } from '@/lib/graph';
import { KIND_LABELS } from '@/lib/labels';
import { useGraph } from '@/lib/queries';
import type { EntityKind, GraphData } from '@/lib/types';
import { useTheme } from '@/app/theme';
import { cn } from 'cn';
import { MaximizeIcon } from 'lucide-react';
import { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { GraphCanvas, type GraphCanvasHandle } from './GraphCanvas';
import { KIND_COLORS, KIND_ICONS } from './kinds';
import { TraceFilters } from './TraceFilters';
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

export function GraphView({ profileId, view }: { profileId: number; view: TraceView }) {
  const graph = useGraph(profileId, view.falsePositives);
  const [selected, select] = useSelectedTrace();
  const hidden = useHidden(graph.data, view.filter);
  const canvas = useRef<GraphCanvasHandle>(null);
  const sourceTitle = useSourceTitle();

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
  if (graph.isError) return <p role="alert">{errorMessage(graph.error)}</p>;
  const data = graph.data;
  const show = (id: number) => {
    select(id);
    canvas.current?.show(id);
  };

  return (
    <div className="grid gap-3">
      <TraceToolbar data={data} view={view} hidden={hidden} onPick={show}>
        <Button variant="ghost" onClick={() => canvas.current?.fit()}>
          <MaximizeIcon aria-hidden />
          Tout voir
        </Button>
      </TraceToolbar>
      {data.truncated && (
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
          {data.nodes.length <= 1 ? (
            <p className="p-6 text-sm text-muted-foreground">
              Rien à relier pour l’instant : lance un scan, les traces apparaîtront ici au fil de
              l’eau.
            </p>
          ) : (
            <GraphCanvas
              ref={canvas}
              profileId={profileId}
              data={data}
              hidden={hidden}
              selected={selected}
              onSelect={select}
              label={`Graphe de ${data.nodes.length} traces. La vue Liste en donne le même contenu.`}
            />
          )}
          <Legend nodes={data.nodes.map((n) => n.kind)} />
        </div>
        {selected !== null && (
          <TracePanel
            key={selected}
            id={selected}
            onSelect={show}
            onClose={() => select(null)}
            sourceTitle={sourceTitle}
          />
        )}
      </div>
    </div>
  );
}

function Legend({ nodes }: { nodes: EntityKind[] }) {
  const { resolved } = useTheme();
  const kinds = useMemo(() => [...new Set(nodes)], [nodes]);
  return (
    <ul
      aria-label="Légende"
      className="absolute bottom-2 left-2 flex max-w-[calc(100%-1rem)] flex-wrap gap-x-3 gap-y-1 rounded-md bg-background/85 px-2 py-1 text-xs"
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
