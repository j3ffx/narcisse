import { t } from '@/i18n';
import { AiLeads } from '@/features/assistant/AiLeads';
import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS, RELATION_LABELS } from '@/lib/labels';
import { useAddSeed, useDismissLead, useLeads, useScans, useUpdateProfile } from '@/lib/queries';
import { formatDay } from '@/lib/remediation';
import { RISK_LEVEL_LABELS, points, riskLevel } from '@/lib/scores';
import type { Lead, ProfileDetail, Rescan, SeedKind } from '@/lib/types';
import { PlusIcon, XIcon } from 'lucide-react';
import { useId } from 'react';
import { toast } from 'sonner';
import { Link } from 'wouter';

const DEPTHS = [0, 1, 2] as const;
const RESCANS: Rescan[] = ['never', 'weekly', 'monthly'];

const INTERVAL_DAYS: Record<Rescan, number | null> = { never: null, weekly: 7, monthly: 30 };

/** Whether the profile is scanned again on its own, and when next. */
export function RescanSetting({ profile }: { profile: ProfileDetail }) {
  const update = useUpdateProfile(profile.id);
  const scans = useScans(profile.id);
  const id = useId();
  const rescan = profile.settings.rescan ?? 'never';
  const last = (scans.data ?? [])
    .filter((s) => !s.notes?.check)
    .map((s) => s.created_at)
    .sort()
    .at(-1);
  const days = INTERVAL_DAYS[rescan];
  const next =
    days !== null && last ? new Date(new Date(last).getTime() + days * 86_400_000) : null;
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-3">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          {t().leads.rescanTitle}
        </h2>
        <p className="text-sm text-muted-foreground">{t().leads.rescanIntro}</p>
      </div>
      <div className="grid w-fit gap-1.5">
        <Label htmlFor={`${id}-rescan`}>{t().leads.rescan}</Label>
        <select
          id={`${id}-rescan`}
          className="h-8 rounded-lg border bg-background px-2 text-sm"
          value={rescan}
          disabled={update.isPending}
          onChange={(e) =>
            update.mutate({
              settings: { ...profile.settings, rescan: e.target.value as Rescan },
            })
          }
        >
          {RESCANS.map((value) => (
            <option key={value} value={value}>
              {t().leads.rescans[value]}
            </option>
          ))}
        </select>
      </div>
      {days !== null && (
        <p className="text-sm" data-testid="next-scan">
          {next ? t().leads.nextScan(formatDay(next.toISOString())) : t().leads.firstScheduled}
        </p>
      )}
    </section>
  );
}

/** Whether scans follow the surest leads by themselves, and how far. */
export function PivotDepth({ profile }: { profile: ProfileDetail }) {
  const update = useUpdateProfile(profile.id);
  const id = useId();
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-3">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          {t().leads.pivotTitle}
        </h2>
        <p className="text-sm text-muted-foreground">{t().leads.pivotIntro}</p>
      </div>
      <div className="grid w-fit gap-1.5">
        <Label htmlFor={`${id}-depth`}>{t().leads.pivot}</Label>
        <select
          id={`${id}-depth`}
          className="h-8 rounded-lg border bg-background px-2 text-sm"
          value={profile.settings.pivot_depth}
          disabled={update.isPending}
          onChange={(e) =>
            update.mutate({
              settings: { ...profile.settings, pivot_depth: Number(e.target.value) },
            })
          }
        >
          {DEPTHS.map((depth) => (
            <option key={depth} value={depth}>
              {t().leads.depths[depth]}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}

/** Traces sure enough to search from: add one as an element, or dismiss it. */
export function Leads({ profileId }: { profileId: number }) {
  const leads = useLeads(profileId);
  const id = useId();
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-3">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          {t().leads.title}
        </h2>
        <p className="text-sm text-muted-foreground">{t().leads.intro}</p>
      </div>
      {leads.isPending && <Pending label={t().leads.loading} />}
      {leads.isError && <p role="alert">{errorMessage(leads.error)}</p>}
      {leads.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">{t().leads.none}</p>
      )}
      {!!leads.data?.length && (
        <ul className="grid gap-2">
          {leads.data.map((lead) => (
            <LeadRow key={lead.entity.id} profileId={profileId} lead={lead} />
          ))}
        </ul>
      )}
      <AiLeads profileId={profileId} />
    </section>
  );
}

function LeadRow({ profileId, lead }: { profileId: number; lead: Lead }) {
  const add = useAddSeed(profileId);
  const dismiss = useDismissLead(profileId);
  const { entity, via, relation } = lead;
  const risk = entity.risk ?? 0;
  return (
    <li
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"
      data-testid="lead"
    >
      <div className="grid min-w-0 gap-0.5">
        <p className="flex min-w-0 items-baseline gap-2">
          <span className="shrink-0 text-xs text-muted-foreground">{KIND_LABELS[entity.kind]}</span>
          <Link
            href={`/profils/${profileId}?trace=${entity.id}`}
            className="truncate font-medium underline-offset-2 hover:underline"
          >
            {entity.display}
          </Link>
        </p>
        <p className="text-xs text-muted-foreground">
          {t().leads.scores(
            points(entity.confidence ?? 0),
            RISK_LEVEL_LABELS[riskLevel(risk)],
            points(risk),
          )}
          {via ? ` · ${RELATION_LABELS[relation ?? ''] ?? relation} via ${via.display}` : ''}
        </p>
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={add.isPending}
          onClick={() =>
            add.mutate(
              { kind: entity.kind as SeedKind, value: entity.display },
              {
                onSuccess: () => toast.success(t().seeds.added),
                onError: (error) => toast.error(errorMessage(error)),
              },
            )
          }
        >
          <PlusIcon aria-hidden />
          {t().seeds.addAsElement}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={dismiss.isPending}
          aria-label={t().leads.dismissLead(entity.display)}
          onClick={() => dismiss.mutate(entity.id)}
        >
          <XIcon aria-hidden />
          {t().leads.dismiss}
        </Button>
      </div>
    </li>
  );
}
