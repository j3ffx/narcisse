import { Pending } from '@/components/Pending';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS } from '@/lib/labels';
import { useDiff } from '@/lib/queries';
import { formatDate } from '@/lib/time';
import type { Entity, Scan } from '@/lib/types';
import { useId, useState } from 'react';
import { Link } from 'wouter';

const GROUPS: { key: 'new' | 'gone' | 'modified' | 'unchecked'; title: string; what: string }[] = [
  { key: 'new', title: 'Nouvelles', what: 'Vues pour la première fois.' },
  {
    key: 'gone',
    title: 'Disparues',
    what: 'Les recherches qui les avaient trouvées sont repassées sans erreur, sans les revoir.',
  },
  { key: 'modified', title: 'Modifiées', what: 'La page ou le profil a changé de contenu.' },
  {
    key: 'unchecked',
    title: 'Non revérifiées',
    what: 'Pas revues, mais leurs recherches ne sont pas toutes repassées : rien à en conclure.',
  },
];

/** What changed between two of the profile's finished scans (the checks of one trace left
 * out). */
export function ScanDiff({ profileId, scans }: { profileId: number; scans: Scan[] }) {
  const id = useId();
  const comparable = scans
    .filter((s) => s.status === 'done' && !s.notes?.check)
    .sort((a, b) => a.id - b.id);
  const [before, setBefore] = useState<number | null>(null);
  const [after, setAfter] = useState<number | null>(null);
  const afterId = after ?? comparable.at(-1)?.id ?? null;
  const beforeId = before ?? comparable.filter((s) => s.id < (afterId ?? 0)).at(-1)?.id ?? null;
  const diff = useDiff(profileId, beforeId, afterId);
  if (comparable.length < 2) return null;

  const options = (pick: (s: Scan) => boolean) =>
    comparable.filter(pick).map((s) => (
      <option key={s.id} value={s.id}>
        {formatDate(s.created_at)} · {s.results_count} résultat{s.results_count > 1 ? 's' : ''}
      </option>
    ));

  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-3" data-testid="scan-diff">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          Ce qui a changé
        </h2>
        <p className="text-sm text-muted-foreground">
          Entre deux scans terminés (les vérifications d’une seule trace ne comptent pas).
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <div className="grid gap-1">
          <Label htmlFor={`${id}-before`}>Du scan</Label>
          <select
            id={`${id}-before`}
            className="h-8 rounded-lg border bg-background px-2 text-sm"
            value={beforeId ?? ''}
            onChange={(e) => setBefore(Number(e.target.value))}
          >
            {options((s) => s.id < (afterId ?? Infinity))}
          </select>
        </div>
        <div className="grid gap-1">
          <Label htmlFor={`${id}-after`}>au scan</Label>
          <select
            id={`${id}-after`}
            className="h-8 rounded-lg border bg-background px-2 text-sm"
            value={afterId ?? ''}
            onChange={(e) => {
              setAfter(Number(e.target.value));
              setBefore(null);
            }}
          >
            {options((s) => s.id > comparable[0]!.id)}
          </select>
        </div>
      </div>
      {diff.isPending && <Pending label="Comparaison…" />}
      {diff.isError && <p role="alert">{errorMessage(diff.error)}</p>}
      {diff.data && (
        <div className="grid gap-4 sm:grid-cols-2">
          {GROUPS.map(({ key, title, what }) => (
            <DiffGroup
              key={key}
              profileId={profileId}
              title={title}
              what={what}
              traces={diff.data[key]}
              testId={`diff-${key}`}
            />
          ))}
        </div>
      )}
    </section>
  );
}

const SHOWN = 20;

function DiffGroup({
  profileId,
  title,
  what,
  traces,
  testId,
}: {
  profileId: number;
  title: string;
  what: string;
  traces: Entity[];
  testId: string;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? traces : traces.slice(0, SHOWN);
  return (
    <div className="grid content-start gap-1.5 rounded-lg border p-3" data-testid={testId}>
      <h3 className="text-sm font-semibold">
        {title} ({traces.length})
      </h3>
      <p className="text-xs text-muted-foreground">{what}</p>
      {traces.length > 0 && (
        <ul className="grid gap-1 text-sm">
          {shown.map((trace) => (
            <li key={trace.id} className="flex min-w-0 items-baseline gap-2">
              <span className="shrink-0 text-xs text-muted-foreground">
                {KIND_LABELS[trace.kind]}
              </span>
              <Link
                href={`/profils/${profileId}?trace=${trace.id}`}
                className="truncate underline-offset-2 hover:underline"
                title={trace.display}
              >
                {trace.display}
              </Link>
            </li>
          ))}
        </ul>
      )}
      {traces.length > SHOWN && !all && (
        <button
          type="button"
          className="w-fit text-xs underline underline-offset-2"
          onClick={() => setAll(true)}
        >
          Tout afficher ({traces.length})
        </button>
      )}
    </div>
  );
}
