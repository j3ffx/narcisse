import { Pending } from '@/components/Pending';
import { useDelayed } from '@/hooks/useDelayed';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS, RELATION_LABELS } from '@/lib/labels';
import { useModules, useResults, useScan } from '@/lib/queries';
import { formatDate, useNow } from '@/lib/time';
import type { EntityKind, Result } from '@/lib/types';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ExternalLinkIcon } from 'lucide-react';
import { useDeferredValue, useRef, useState } from 'react';
import { Link } from 'wouter';
import { RunRow } from './RunRow';
import { ScanControls } from './ScanControls';
import { ScanStatusBadge } from './status';

const ALL = 'all';
const RESULT_KINDS: EntityKind[] = [
  'account',
  'url',
  'email',
  'username',
  'domain',
  'phone',
  'name',
];

export function ScanPage({ id }: { id: number }) {
  const scan = useScan(id);
  const now = useNow();
  if (scan.isPending) return <Pending label="Chargement du scan…" />;
  if (scan.isError) return <p role="alert">{errorMessage(scan.error)}</p>;
  const data = scan.data;

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            <Link href={`/profils/${data.profile_id}`} className="hover:underline">
              {data.profile_name}
            </Link>{' '}
            · {formatDate(data.created_at)}
          </p>
          <h1 className="flex flex-wrap items-center gap-3 font-heading text-2xl font-semibold">
            Scan
            <ScanStatusBadge status={data.status} />
          </h1>
        </div>
        <ScanControls scan={data} size="default" />
      </div>
      <section aria-labelledby="runs-title" className="grid gap-2">
        <h2 id="runs-title" className="font-heading text-lg font-semibold">
          Recherches
        </h2>
        <ul className="divide-y rounded-lg border px-3">
          {data.runs.map((run) => (
            <RunRow key={run.id} run={run} now={now} />
          ))}
        </ul>
      </section>
      <Results scanId={id} live={data.status === 'running'} />
    </div>
  );
}

function Results({ scanId, live }: { scanId: number; live: boolean }) {
  const [kind, setKind] = useState<string>(ALL);
  const [search, setSearch] = useState('');
  // Typing stays instant; the server-side filter follows the deferred value.
  const q = useDeferredValue(search);
  const results = useResults(scanId, kind === ALL ? null : kind, q);
  const filtering = useDelayed(results.isFetching && !results.isPending);
  const items = results.data?.items ?? [];
  const total = results.data?.total ?? 0;

  return (
    <section aria-labelledby="results-title" className="grid gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="results-title" className="font-heading text-lg font-semibold">
          Résultats{' '}
          <span className="text-base font-normal text-muted-foreground" aria-live="polite">
            ({total}
            {live ? ', en direct' : ''})
          </span>
        </h2>
        <div className="flex flex-wrap gap-2">
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger className="w-40" aria-label="Type de résultat">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Tous les types</SelectItem>
              {RESULT_KINDS.map((k) => (
                <SelectItem key={k} value={k}>
                  {KIND_LABELS[k]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="search"
            className="w-56"
            placeholder="Chercher dans les résultats"
            aria-label="Chercher dans les résultats"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>
      {filtering && (
        <p role="status" className="text-sm text-muted-foreground">
          Filtrage des résultats…
        </p>
      )}
      {results.isPending && <Pending label="Chargement des résultats…" />}
      {results.isError && <p role="alert">{errorMessage(results.error)}</p>}
      {results.data && items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {live ? 'Les résultats apparaîtront ici dès qu’ils arrivent.' : 'Aucun résultat.'}
        </p>
      )}
      {items.length > 0 && <ResultList items={items} />}
      {items.length < total && (
        <p className="text-sm text-muted-foreground">
          {items.length} résultats affichés sur {total} : affine le filtre pour voir les autres.
        </p>
      )}
    </section>
  );
}

const ROW_HEIGHT = 76;

/** Only the rows near the viewport exist in the page: thousands of results scroll smoothly. */
function ResultList({ items }: { items: Result[] }) {
  const parent = useRef<HTMLDivElement>(null);
  const modules = useModules();
  const titles = new Map(modules.data?.map((m) => [m.name, m.title]));
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual is fine here
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parent.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  return (
    <div
      ref={parent}
      className="max-h-[32rem] overflow-y-auto rounded-lg border"
      tabIndex={0}
      aria-label="Liste des résultats"
    >
      <ul className="relative" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((row) => {
          const result = items[row.index]!;
          return (
            <li
              key={result.id}
              data-testid="result"
              className="absolute inset-x-0 flex flex-col justify-center gap-0.5 border-b px-3 motion-safe:animate-in motion-safe:fade-in"
              style={{ height: ROW_HEIGHT, transform: `translateY(${row.start}px)` }}
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="shrink-0 rounded bg-muted px-1.5 text-xs text-muted-foreground">
                  {KIND_LABELS[result.entity.kind]}
                </span>
                <span className="truncate font-medium">{result.entity.display}</span>
                {result.url && (
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="shrink-0 text-muted-foreground hover:text-foreground"
                    aria-label={`Ouvrir ${result.url}`}
                  >
                    <ExternalLinkIcon aria-hidden className="size-4" />
                  </a>
                )}
              </div>
              <p className="truncate text-xs text-muted-foreground">
                {result.relation ? `${RELATION_LABELS[result.relation] ?? result.relation} · ` : ''}
                {titles.get(result.module) ?? result.module}
                {result.confidence !== null &&
                  ` · confiance ${Math.round(result.confidence * 100)} %`}
              </p>
              {result.excerpt && (
                <p className="truncate text-xs text-muted-foreground">{result.excerpt}</p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
