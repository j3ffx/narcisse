import { Pending } from '@/components/Pending';
import { useDelayed } from '@/hooks/useDelayed';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS } from '@/lib/labels';
import { useResults, useScan } from '@/lib/queries';
import { formatDate, useNow } from '@/lib/time';
import type { EntityKind } from '@/lib/types';
import { useDeferredValue, useState } from 'react';
import { Link } from 'wouter';
import { ResultList } from './ResultList';
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
        {!!(data.notes?.pivots || data.notes?.capped?.length) && (
          <p className="text-sm text-muted-foreground" data-testid="scan-pivots">
            {pivotSummary(data.notes.pivots ?? 0, data.notes.capped?.length ?? 0)}
          </p>
        )}
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

/** « 3 pistes suivies · 2 laissées (plafond de 25 par scan atteint) ». */
function pivotSummary(followed: number, capped: number): string {
  const parts = [`${followed} piste${followed > 1 ? 's' : ''} suivie${followed > 1 ? 's' : ''}`];
  if (capped) {
    parts.push(
      `${capped} laissée${capped > 1 ? 's' : ''} (plafond de 25 par scan atteint : ajoute-les ` +
        `comme éléments si tu veux qu’elles soient fouillées)`,
    );
  }
  return parts.join(' · ');
}

function Results({ scanId, live }: { scanId: number; live: boolean }) {
  const [kind, setKind] = useState<string>(ALL);
  const [search, setSearch] = useState('');
  const [falsePositives, setFalsePositives] = useState(false);
  // Typing stays instant; the server-side filter follows the deferred value.
  const q = useDeferredValue(search);
  const results = useResults(scanId, { kind: kind === ALL ? null : kind, q, falsePositives });
  const filtering = useDelayed(results.isFetching && !results.isPending);
  // A trace marked "not me" leaves the list at once, before the next fetch.
  const items = (results.data?.items ?? []).filter(
    (r) => falsePositives || r.entity.status !== 'false_positive',
  );
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
          <Label className="flex items-center gap-2 text-sm font-normal">
            <Checkbox
              checked={falsePositives}
              onCheckedChange={(checked) => setFalsePositives(checked === true)}
            />
            Afficher les « pas moi »
          </Label>
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
