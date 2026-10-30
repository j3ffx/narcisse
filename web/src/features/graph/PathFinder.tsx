import { t } from '@/i18n';
import { Button } from '@/components/ui/button';
import { shortestPath, type GraphPath } from '@/lib/graph';
import { RELATION_LABELS } from '@/lib/labels';
import type { GraphData } from '@/lib/types';
import { RouteIcon, XIcon } from 'lucide-react';
import { useMemo, useState } from 'react';
import { TraceSearch } from './TraceSearch';

/** "How is this trace related to that one?": the shortest chain between them, in the panel. */
export function PathFinder({
  data,
  from,
  hidden,
  path,
  onPath,
  onShow,
}: {
  data: GraphData;
  from: number;
  hidden: ReadonlySet<number>;
  path: GraphPath | null;
  onPath: (path: GraphPath | null) => void;
  /** Shows a trace of the path (the camera goes to it). */
  onShow: (id: number) => void;
}) {
  const byId = useMemo(() => new Map(data.nodes.map((n) => [n.id, n])), [data]);
  const edges = useMemo(() => new Map(data.edges.map((e) => [e.id, e])), [data]);
  const identity = data.nodes.find((n) => n.kind === 'identity');
  const [missing, setMissing] = useState(false);
  const link = (to: number) => {
    const found = shortestPath(data, from, to, hidden);
    setMissing(found === null);
    onPath(found);
  };

  return (
    <section className="grid gap-2" aria-labelledby="path-title">
      <h3 id="path-title" className="flex items-center gap-1.5 text-sm font-semibold">
        <RouteIcon aria-hidden className="size-4" />
        {t().path.title}
      </h3>
      <div className="flex flex-wrap gap-2">
        <TraceSearch
          nodes={data.nodes.filter((n) => n.id !== from && !hidden.has(n.id))}
          onPick={(node) => link(node.id)}
          label={t().path.linkTo}
          placeholder={t().path.another}
          shortcut={false}
          className="relative min-w-40 flex-1"
        />
        {identity && identity.id !== from && (
          <Button variant="outline" size="sm" onClick={() => link(identity.id)}>
            {t().path.you}
          </Button>
        )}
      </div>
      {missing && (
        <p role="status" className="text-sm text-muted-foreground">
          {t().path.none(hidden.size > 0)}
        </p>
      )}
      {path && (
        <div className="grid gap-1" data-testid="path">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">{t().path.links(path.edges.length)}</p>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={t().path.clear}
              onClick={() => onPath(null)}
            >
              <XIcon aria-hidden />
            </Button>
          </div>
          <ol className="grid gap-0.5 text-sm">
            {path.nodes.map((id, i) => {
              const edge = i > 0 ? edges.get(path.edges[i - 1]!) : undefined;
              const node = byId.get(id);
              return (
                <li key={id} className="grid">
                  {edge && (
                    <span className="pl-3 text-xs text-muted-foreground">
                      {edge.source_id === id ? '↑' : '↓'}{' '}
                      {RELATION_LABELS[edge.relation] ?? edge.relation}
                    </span>
                  )}
                  <button
                    type="button"
                    className="truncate text-left underline-offset-2 hover:underline focus-visible:underline"
                    onClick={() => onShow(id)}
                    title={node?.display}
                  >
                    {node?.display ?? '?'}
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}
