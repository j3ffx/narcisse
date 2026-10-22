import { Pending } from '@/components/Pending';
import { ReviewButtons } from '@/components/ReviewButtons';
import { Button } from '@/components/ui/button';
import { errorMessage } from '@/lib/errors';
import { ENTITY_STATUS_LABELS, KIND_LABELS } from '@/lib/labels';
import { useGraph } from '@/lib/queries';
import { RISK_LEVEL_LABELS, points, riskLevel } from '@/lib/scores';
import { formatDate } from '@/lib/time';
import type { GraphNode } from '@/lib/types';
import { useVirtualizer } from '@tanstack/react-virtual';
import { cn } from 'cn';
import { WaypointsIcon } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { Link } from 'wouter';
import { TraceToolbar } from './GraphView';
import { KIND_ICONS } from './kinds';
import { TracePanel } from './TracePanel';
import { useHidden, useSelectedTrace, useSourceTitle, type TraceView } from './useTraceView';

const ROW_HEIGHT = 68;

type Order = 'recent' | 'risk' | 'confidence';
const ORDERS: [Order, string][] = [
  ['recent', 'les plus récentes'],
  ['risk', 'les plus exposantes'],
  ['confidence', 'les plus sûres'],
];
const byOrder: Record<Order, (a: GraphNode, b: GraphNode) => number> = {
  recent: (a, b) => b.last_seen.localeCompare(a.last_seen),
  risk: (a, b) => (b.risk ?? 0) - (a.risk ?? 0),
  confidence: (a, b) => (b.confidence ?? 0) - (a.confidence ?? 0),
};

/**
 * The graph's traces as a list: the same filters and the same selection as the graph, and
 * everything it shows in a form every reader can follow. Only the rows near the viewport exist.
 */
export function TraceList({ profileId, view }: { profileId: number; view: TraceView }) {
  const graph = useGraph(profileId, view.falsePositives);
  const [selected, select] = useSelectedTrace();
  const hidden = useHidden(graph.data, view.filter);
  const sourceTitle = useSourceTitle();
  const parent = useRef<HTMLDivElement>(null);
  const [order, setOrder] = useState<Order>('recent');

  const rows = useMemo(
    () =>
      (graph.data?.nodes ?? [])
        .filter((n) => !hidden.has(n.id))
        .sort((a, b) => byOrder[order](a, b) || a.id - b.id),
    [graph.data, hidden, order],
  );
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual is fine here
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parent.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  if (graph.isPending) return <Pending label="Chargement des traces…" />;
  if (graph.isError) return <p role="alert">{errorMessage(graph.error)}</p>;
  const pick = (id: number) => {
    select(id);
    const index = rows.findIndex((r) => r.id === id);
    if (index >= 0) virtualizer.scrollToIndex(index, { align: 'center' });
  };

  return (
    <div className="grid gap-3">
      <TraceToolbar data={graph.data} view={view} hidden={hidden} onPick={pick} />
      <label className="flex w-fit items-center gap-2 text-sm">
        Afficher d’abord
        <select
          className="h-8 rounded-lg border bg-background px-2 text-sm"
          value={order}
          onChange={(e) => setOrder(e.target.value as Order)}
          data-testid="trace-order"
        >
          {ORDERS.map(([value, title]) => (
            <option key={value} value={value}>
              {title}
            </option>
          ))}
        </select>
      </label>
      <div
        className={cn(
          'grid h-[calc(100dvh-14rem)] min-h-[28rem] gap-3',
          selected !== null && 'lg:grid-cols-[minmax(0,1fr)_24rem]',
        )}
      >
        <div
          ref={parent}
          className="min-h-[24rem] overflow-y-auto rounded-lg border"
          tabIndex={0}
          aria-label="Liste des traces"
        >
          <ul className="relative" style={{ height: virtualizer.getTotalSize() }}>
            {virtualizer.getVirtualItems().map((row) => {
              const node = rows[row.index]!;
              const Icon = KIND_ICONS[node.kind];
              const active = node.id === selected;
              return (
                <li
                  key={node.id}
                  data-testid="trace"
                  data-status={node.status}
                  className={cn(
                    'absolute inset-x-0 flex items-center gap-3 border-b px-3',
                    active && 'bg-accent',
                    node.status === 'false_positive' && 'opacity-60',
                  )}
                  style={{ height: ROW_HEIGHT, transform: `translateY(${row.start}px)` }}
                >
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left"
                    aria-current={active || undefined}
                    onClick={() => select(active ? null : node.id)}
                  >
                    <span className="flex max-w-full items-center gap-2">
                      <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                      <span className="sr-only">{KIND_LABELS[node.kind]} :</span>
                      <span className="truncate font-medium">{node.display}</span>
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {KIND_LABELS[node.kind]} ·{' '}
                      {node.modules
                        .map((m) => (m === 'seed' ? 'déclaré par toi' : sourceTitle(m)))
                        .join(', ')}{' '}
                      · {ENTITY_STATUS_LABELS[node.status]}
                      {node.risk !== null && node.kind !== 'identity'
                        ? ` · risque ${RISK_LEVEL_LABELS[riskLevel(node.risk)]} (${points(node.risk)})`
                        : ''}{' '}
                      · vue le {formatDate(node.last_seen)}
                    </span>
                  </button>
                  {node.kind !== 'identity' && <ReviewButtons entity={node} />}
                </li>
              );
            })}
          </ul>
          {rows.length === 0 && (
            <p className="p-6 text-sm text-muted-foreground">Aucune trace avec ces filtres.</p>
          )}
        </div>
        {selected !== null && (
          <TracePanel
            profileId={profileId}
            key={selected}
            id={selected}
            onSelect={pick}
            onClose={() => select(null)}
            sourceTitle={sourceTitle}
            actions={
              <Button variant="outline" size="sm" asChild className="w-fit">
                <Link href={`/profils/${profileId}?trace=${selected}`}>
                  <WaypointsIcon aria-hidden />
                  Voir dans le graphe
                </Link>
              </Button>
            }
          />
        )}
      </div>
    </div>
  );
}
