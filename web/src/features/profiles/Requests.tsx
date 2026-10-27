import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { LevelDot } from '@/features/graph/Scores';
import { errorMessage } from '@/lib/errors';
import {
  useCheckRequest,
  useExposure,
  useReminder,
  useRequests,
  useStopFollowing,
  useUpdateRequest,
} from '@/lib/queries';
import {
  REQUEST_STATUS_LABELS,
  actionText,
  checkText,
  formatDay,
  letterText,
  mailtoHref,
  requestSummary,
} from '@/lib/remediation';
import { RISK_LEVEL_LABELS, type RiskLevel } from '@/lib/scores';
import type { Exposure, FollowedRequest, Lang, RequestStatus } from '@/lib/types';
import { BellRingIcon, CopyIcon, MailIcon, RefreshCwIcon, Trash2Icon } from 'lucide-react';
import { useId, useState } from 'react';
import { toast } from 'sonner';
import { Link, useLocation } from 'wouter';

const LEVELS: RiskLevel[] = ['critical', 'high', 'medium', 'low'];

/** The profile's « À faire »: its exposure, and the actions the user follows. */
export function Requests({ profileId }: { profileId: number }) {
  const requests = useRequests(profileId);
  const exposure = useExposure(profileId);
  return (
    <div className="grid gap-8">
      {exposure.data && <ExposureSummary exposure={exposure.data} />}
      {exposure.isError && <p role="alert">{errorMessage(exposure.error)}</p>}
      {requests.isPending && <Pending label="Chargement de tes demandes…" />}
      {requests.isError && <p role="alert">{errorMessage(requests.error)}</p>}
      {requests.data && <RequestGroups profileId={profileId} requests={requests.data} />}
    </div>
  );
}

function ExposureSummary({ exposure }: { exposure: Exposure }) {
  const id = useId();
  const traces = LEVELS.reduce((sum, level) => sum + (exposure.levels[level] ?? 0), 0);
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-3" data-testid="exposure">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          Ton exposition
        </h2>
        <p className="text-sm text-muted-foreground">
          Les traces qui sont à toi (ou pas encore triées) et que l’on trouve encore en public, par
          niveau de risque. Une trace qu’un scan ne trouve plus après ta demande en sort.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-6">
        <ul className="flex flex-wrap gap-4" aria-label="Traces par niveau de risque">
          {LEVELS.map((level) => (
            <li key={level} className="grid gap-0.5" data-level={level}>
              <span className="font-heading text-2xl font-semibold">
                {exposure.levels[level] ?? 0}
              </span>
              <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <LevelDot level={level} />
                {RISK_LEVEL_LABELS[level]}
              </span>
            </li>
          ))}
        </ul>
        <History exposure={exposure} />
      </div>
      <p className="text-sm text-muted-foreground">
        {traces} trace{traces > 1 ? 's' : ''} exposée{traces > 1 ? 's' : ''} ·{' '}
        {exposure.requests.sent + exposure.requests.waiting} demande
        {exposure.requests.sent + exposure.requests.waiting > 1 ? 's' : ''} en cours
        {exposure.due > 0 ? ` · ${exposure.due} à relancer` : ''}
        {exposure.gone > 0
          ? ` · ${exposure.gone} trace${exposure.gone > 1 ? 's' : ''} disparue${exposure.gone > 1 ? 's' : ''}`
          : ''}
      </p>
    </section>
  );
}

/** The exposure scan after scan, as a line (its first and last values are also written). */
function History({ exposure }: { exposure: Exposure }) {
  const points = exposure.history;
  if (points.length < 2) {
    return (
      <p className="text-sm text-muted-foreground">
        L’évolution apparaîtra après ton prochain scan.
      </p>
    );
  }
  const width = 220;
  const height = 48;
  const values = points.map((p) => p.exposure);
  const min = Math.min(...values);
  const range = Math.max(...values) - min;
  const step = width / (points.length - 1);
  // A flat exposure draws a level line in the middle.
  const y = (v: number) => (range ? height - 2 - ((v - min) / range) * (height - 4) : height / 2);
  const line = values.map((v, i) => `${(i * step).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const first = points[0]!;
  const last = points[points.length - 1]!;
  const summary = `Exposition : ${first.exposure.toLocaleString('fr-FR')} au scan du ${formatDay(first.taken_at)}, ${last.exposure.toLocaleString('fr-FR')} au scan du ${formatDay(last.taken_at)}.`;
  return (
    <figure className="grid gap-1">
      <svg
        role="img"
        aria-label={summary}
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        className="text-primary"
      >
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={line} />
      </svg>
      <figcaption className="text-xs text-muted-foreground">
        Exposition {first.exposure.toLocaleString('fr-FR')} →{' '}
        {last.exposure.toLocaleString('fr-FR')}, sur tes {points.length} derniers scans
      </figcaption>
    </figure>
  );
}

const GROUPS: { title: string; pick: (r: FollowedRequest) => boolean }[] = [
  { title: 'À relancer', pick: (r) => r.due },
  { title: 'En cours', pick: (r) => !r.due && (r.status === 'sent' || r.status === 'waiting') },
  { title: 'À faire', pick: (r) => r.status === 'todo' },
  { title: 'Terminées', pick: (r) => r.status === 'done' || r.status === 'refused' },
];

function RequestGroups({
  profileId,
  requests,
}: {
  profileId: number;
  requests: FollowedRequest[];
}) {
  if (requests.length === 0) {
    return (
      <section className="grid gap-2">
        <h2 className="font-heading text-lg font-semibold">Tes demandes</h2>
        <p className="text-sm text-muted-foreground">
          Rien à suivre pour l’instant. Dans le détail d’une trace, « Que faire ? » te dit quoi
          faire ; « Ajouter à « À faire » » ou « Je l’ai envoyée » la fait suivre ici.
        </p>
      </section>
    );
  }
  return (
    <>
      {GROUPS.map(({ title, pick }) => {
        const items = requests.filter(pick);
        if (items.length === 0) return null;
        return (
          <section key={title} className="grid gap-2" data-testid="request-group">
            <h2 className="font-heading text-lg font-semibold">
              {title} ({items.length})
            </h2>
            <ul className="grid gap-2">
              {items.map((request) => (
                <RequestRow key={request.id} profileId={profileId} request={request} />
              ))}
            </ul>
          </section>
        );
      })}
    </>
  );
}

function RequestRow({ profileId, request }: { profileId: number; request: FollowedRequest }) {
  const id = useId();
  const update = useUpdateRequest(profileId);
  const stop = useStopFollowing(profileId);
  const check = useCheckRequest();
  const [, navigate] = useLocation();
  const text = actionText(request.action);
  const checked = checkText(request);
  return (
    <li className="grid gap-2 rounded-lg border p-3 text-sm" data-testid="request">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="grid gap-0.5">
          <span className="font-medium">
            {text.title}
            {request.service ? ` · ${request.service}` : ''}
          </span>
          <Link
            href={`/profils/${profileId}?trace=${request.entity.id}`}
            className="break-all text-muted-foreground underline underline-offset-2"
          >
            {request.entity.display}
          </Link>
        </p>
        <div className="grid gap-1">
          <Label htmlFor={`${id}-status`} className="sr-only">
            Statut
          </Label>
          <select
            id={`${id}-status`}
            value={request.status}
            onChange={(e) =>
              update.mutate({ id: request.id, status: e.target.value as RequestStatus })
            }
            className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm dark:bg-input/30"
          >
            {Object.entries(REQUEST_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="text-muted-foreground" data-testid="request-summary">
        {requestSummary(request)}
        {request.recipient ? ` · à ${request.recipient}` : ''}
      </p>
      {checked && (
        <p className={request.check === 'gone' ? 'font-medium' : ''} data-testid="request-check">
          {checked}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {request.due && <ReminderDialog profileId={profileId} request={request} />}
        {request.status !== 'refused' && request.check !== 'gone' && (
          <Button
            size="sm"
            variant="outline"
            disabled={check.isPending}
            onClick={() =>
              check.mutate(request.id, {
                onSuccess: (scan) => {
                  toast.success(
                    'Vérification lancée : les recherches qui l’avaient trouvée repassent.',
                    {
                      action: { label: 'Voir', onClick: () => navigate(`/scans/${scan.id}`) },
                    },
                  );
                },
              })
            }
          >
            <RefreshCwIcon aria-hidden />
            Vérifier maintenant
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          disabled={stop.isPending}
          onClick={() => stop.mutate(request.id)}
        >
          <Trash2Icon aria-hidden />
          Ne plus suivre
        </Button>
      </div>
    </li>
  );
}

const LANG_LABELS: Record<Lang, string> = { fr: 'Français', en: 'English' };

/** The reminder of a request unanswered for a month, the request copied below it. */
function ReminderDialog({ profileId, request }: { profileId: number; request: FollowedRequest }) {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<Lang>('fr');
  const reminder = useReminder(request.id, open);
  const update = useUpdateRequest(profileId);
  const letter = reminder.data?.[lang];
  const href = letter ? mailtoHref(request.recipient ?? '', letter.subject, letter.body) : '';
  const copy = async (done = 'Texte copié.') => {
    if (!letter) return;
    try {
      await navigator.clipboard.writeText(letterText(letter.subject, letter.body));
      toast.success(done);
    } catch {
      toast.error('Copie impossible : sélectionne le texte et copie-le à la main.');
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <BellRingIcon aria-hidden />
          Préparer la relance
        </Button>
      </DialogTrigger>
      <DialogContent className="grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Relance</DialogTitle>
          <DialogDescription>
            Un mois sans réponse : le RGPD te permet de relancer, puis de saisir la CNIL. Narcisse
            n’envoie rien.
          </DialogDescription>
        </DialogHeader>
        <div className="-mx-4 grid content-start gap-3 overflow-y-auto px-4">
          <div role="group" aria-label="Langue de la relance" className="flex gap-2">
            {(['fr', 'en'] as const).map((option) => (
              <Button
                key={option}
                size="sm"
                variant={lang === option ? 'secondary' : 'ghost'}
                aria-pressed={lang === option}
                onClick={() => setLang(option)}
              >
                {LANG_LABELS[option]}
              </Button>
            ))}
          </div>
          {reminder.isPending && <Pending label="Préparation de la relance…" />}
          {reminder.isError && <p role="alert">{errorMessage(reminder.error)}</p>}
          {letter && (
            <pre
              className="whitespace-pre-wrap rounded-lg border p-3 font-sans text-sm"
              data-testid="reminder-text"
            >
              {letterText(letter.subject, letter.body)}
            </pre>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => void copy()} disabled={!letter}>
            <CopyIcon aria-hidden />
            Copier le texte
          </Button>
          {letter && (
            <Button asChild variant="outline">
              <a
                href={href}
                onClick={() => {
                  // Too long for a link: the text goes through the clipboard.
                  if (!href.includes('&body='))
                    void copy('Texte copié : colle-le dans le message.');
                }}
              >
                <MailIcon aria-hidden />
                Ouvrir dans ma messagerie
              </a>
            </Button>
          )}
          <Button
            disabled={update.isPending}
            onClick={() =>
              update.mutate(
                { id: request.id, reminded: true },
                {
                  onSuccess: () => {
                    setOpen(false);
                    toast.success('Relance notée : la prochaine sera proposée dans un mois.');
                  },
                },
              )
            }
          >
            C’est envoyé
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
