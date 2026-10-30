import { num, t } from '@/i18n';
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
      {requests.isPending && <Pending label={t().requests.loading} />}
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
          {t().requests.exposure}
        </h2>
        <p className="text-sm text-muted-foreground">{t().requests.exposureIntro}</p>
      </div>
      <div className="flex flex-wrap items-end gap-6">
        <ul className="flex flex-wrap gap-4" aria-label={t().requests.byLevel}>
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
        {t().requests.counts(
          traces,
          exposure.requests.sent + exposure.requests.waiting,
          exposure.due,
          exposure.gone,
        )}
      </p>
    </section>
  );
}

/** The exposure scan after scan, as a line (its first and last values are also written). */
function History({ exposure }: { exposure: Exposure }) {
  const points = exposure.history;
  if (points.length < 2) {
    return <p className="text-sm text-muted-foreground">{t().requests.historyLater}</p>;
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
  const summary = t().requests.historySummary(
    num(first.exposure),
    formatDay(first.taken_at),
    num(last.exposure),
    formatDay(last.taken_at),
  );
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
        {t().requests.historyCaption(num(first.exposure), num(last.exposure), points.length)}
      </figcaption>
    </figure>
  );
}

const GROUPS: {
  key: 'due' | 'running' | 'todo' | 'done';
  pick: (r: FollowedRequest) => boolean;
}[] = [
  { key: 'due', pick: (r) => r.due },
  { key: 'running', pick: (r) => !r.due && (r.status === 'sent' || r.status === 'waiting') },
  { key: 'todo', pick: (r) => r.status === 'todo' },
  { key: 'done', pick: (r) => r.status === 'done' || r.status === 'refused' },
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
        <h2 className="font-heading text-lg font-semibold">{t().requests.yours}</h2>
        <p className="text-sm text-muted-foreground">{t().requests.none}</p>
      </section>
    );
  }
  return (
    <>
      {GROUPS.map(({ key, pick }) => {
        const items = requests.filter(pick);
        if (items.length === 0) return null;
        return (
          <section key={key} className="grid gap-2" data-testid="request-group">
            <h2 className="font-heading text-lg font-semibold">
              {t().requests.groups[key]} ({items.length})
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
            {t().requests.status}
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
        {request.recipient ? ` · ${t().requests.to(request.recipient)}` : ''}
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
                  toast.success(t().requests.checkStarted, {
                    action: {
                      label: t().requests.see,
                      onClick: () => navigate(`/scans/${scan.id}`),
                    },
                  });
                },
              })
            }
          >
            <RefreshCwIcon aria-hidden />
            {t().requests.checkNow}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          disabled={stop.isPending}
          onClick={() => stop.mutate(request.id)}
        >
          <Trash2Icon aria-hidden />
          {t().requests.stop}
        </Button>
      </div>
    </li>
  );
}

const LANG_LABELS: Record<Lang, string> = { fr: 'Français', en: 'English' }; // in their own language

/** The reminder of a request unanswered for a month, the request copied below it. */
function ReminderDialog({ profileId, request }: { profileId: number; request: FollowedRequest }) {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<Lang>('fr');
  const reminder = useReminder(request.id, open);
  const update = useUpdateRequest(profileId);
  const letter = reminder.data?.[lang];
  const href = letter ? mailtoHref(request.recipient ?? '', letter.subject, letter.body) : '';
  const copy = async (done = t().letters.copied) => {
    if (!letter) return;
    try {
      await navigator.clipboard.writeText(letterText(letter.subject, letter.body, lang));
      toast.success(done);
    } catch {
      toast.error(t().letters.copyFailed);
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <BellRingIcon aria-hidden />
          {t().requests.prepareReminder}
        </Button>
      </DialogTrigger>
      <DialogContent className="grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t().requests.reminder}</DialogTitle>
          <DialogDescription>{t().requests.reminderIntro}</DialogDescription>
        </DialogHeader>
        <div className="-mx-4 grid content-start gap-3 overflow-y-auto px-4">
          <div role="group" aria-label={t().requests.reminderLang} className="flex gap-2">
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
          {reminder.isPending && <Pending label={t().requests.preparing} />}
          {reminder.isError && <p role="alert">{errorMessage(reminder.error)}</p>}
          {letter && (
            <pre
              className="whitespace-pre-wrap rounded-lg border p-3 font-sans text-sm"
              data-testid="reminder-text"
            >
              {letterText(letter.subject, letter.body, lang)}
            </pre>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => void copy()} disabled={!letter}>
            <CopyIcon aria-hidden />
            {t().letters.copy}
          </Button>
          {letter && (
            <Button asChild variant="outline">
              <a
                href={href}
                onClick={() => {
                  // Too long for a link: the text goes through the clipboard.
                  if (!href.includes('&body=')) void copy(t().letters.copiedPaste);
                }}
              >
                <MailIcon aria-hidden />
                {t().letters.openMail}
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
                    toast.success(t().requests.reminded);
                  },
                },
              )
            }
          >
            {t().requests.sent}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
