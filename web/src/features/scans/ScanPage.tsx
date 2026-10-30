import { t } from '@/i18n';
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
import { ArrowLeftIcon } from 'lucide-react';
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
  if (scan.isPending) return <Pending label={t().scanPage.loading} />;
  if (scan.isError) return <p role="alert">{errorMessage(scan.error)}</p>;
  const data = scan.data;

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            href={`/profils/${data.profile_id}`}
            className="inline-flex items-center gap-1 text-sm font-medium underline underline-offset-2"
          >
            <ArrowLeftIcon aria-hidden className="size-4" />
            {data.profile_name}
          </Link>
          <p className="text-sm text-muted-foreground">{formatDate(data.created_at)}</p>
          <h1 className="flex flex-wrap items-center gap-3 font-heading text-2xl font-semibold">
            {t().scanPage.title}
            <ScanStatusBadge status={data.status} />
          </h1>
        </div>
        <ScanControls scan={data} size="default" />
      </div>
      {data.notes?.changes && (
        <p className="text-sm" data-testid="scan-changes">
          {data.notes.scheduled ? `${t().scanPage.scheduled} ` : ''}
          {t().scanPage.since} {changesText(data.notes.changes)}{' '}
          <Link href={`/profils/${data.profile_id}/scans`} className="underline underline-offset-2">
            {t().scanPage.details}
          </Link>
        </p>
      )}
      {data.notes?.check && (
        <p className="text-sm" data-testid="scan-check">
          {t().scanPage.check(String(data.notes.trace))}
        </p>
      )}
      <section aria-labelledby="runs-title" className="grid gap-2">
        <h2 id="runs-title" className="font-heading text-lg font-semibold">
          {t().scanPage.runs}
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
  const parts = [t().scanPage.followed(followed)];
  if (capped) parts.push(t().scanPage.capped(capped));
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
          {t().scanPage.results}{' '}
          <span className="text-base font-normal text-muted-foreground" aria-live="polite">
            ({total}
            {live ? `, ${t().scanPage.live}` : ''})
          </span>
        </h2>
        <div className="flex flex-wrap gap-2">
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger className="w-40" aria-label={t().scanPage.resultKind}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{t().scanPage.allKinds}</SelectItem>
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
            placeholder={t().scanPage.search}
            aria-label={t().scanPage.search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Label className="flex items-center gap-2 text-sm font-normal">
            <Checkbox
              checked={falsePositives}
              onCheckedChange={(checked) => setFalsePositives(checked === true)}
            />
            {t().scanPage.showNotMe}
          </Label>
        </div>
      </div>
      {filtering && (
        <p role="status" className="text-sm text-muted-foreground">
          {t().scanPage.filtering}
        </p>
      )}
      {results.isPending && <Pending label={t().scanPage.loadingResults} />}
      {results.isError && <p role="alert">{errorMessage(results.error)}</p>}
      {results.data && items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {live ? t().scanPage.willAppear : t().scanPage.noResult}
        </p>
      )}
      {items.length > 0 && <ResultList items={items} />}
      {items.length < total && (
        <p className="text-sm text-muted-foreground">{t().scanPage.shown(items.length, total)}</p>
      )}
    </section>
  );
}

/** « 3 nouvelles traces, 1 disparue » (as the tray says it). */
function changesText(changes: { new: number; gone: number; modified: number }): string {
  const say = t().scanPage;
  const parts: string[] = [];
  if (changes.new) parts.push(say.newTraces(changes.new));
  if (changes.gone) parts.push(say.gone(changes.gone));
  if (changes.modified) parts.push(say.modified(changes.modified));
  return parts.length ? `${parts.join(', ')}.` : say.nothingNew;
}
