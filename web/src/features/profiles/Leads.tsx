import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS, RELATION_LABELS } from '@/lib/labels';
import { useAddSeed, useDismissLead, useLeads, useUpdateProfile } from '@/lib/queries';
import { RISK_LEVEL_LABELS, points, riskLevel } from '@/lib/scores';
import type { Lead, ProfileDetail, SeedKind } from '@/lib/types';
import { PlusIcon, XIcon } from 'lucide-react';
import { useId } from 'react';
import { toast } from 'sonner';
import { Link } from 'wouter';

const DEPTHS: [number, string][] = [
  [0, 'Non : je valide chaque piste'],
  [1, 'Oui, à un saut des éléments'],
  [2, 'Oui, jusqu’à deux sauts'],
];

/** Whether scans follow the surest leads by themselves, and how far. */
export function PivotDepth({ profile }: { profile: ProfileDetail }) {
  const update = useUpdateProfile(profile.id);
  const id = useId();
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-3">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          Suivre les pistes pendant les scans
        </h2>
        <p className="text-sm text-muted-foreground">
          Une piste est une trace trouvée qui pourrait servir de point de départ (un email lu dans
          un profil, un domaine cité dans une bio…). Par défaut, Narcisse te les propose ci-dessus
          et tu choisis. Il peut aussi suivre de lui-même les plus sûres (confiance d’au moins 70),
          25 au plus par scan, jamais une trace que tu as rejetée ; les sources « actif léger » ne
          reçoivent qu’une piste que tu as confirmée ou presque certaine (85 et plus).
        </p>
      </div>
      <div className="grid w-fit gap-1.5">
        <Label htmlFor={`${id}-depth`}>Suivre les pistes sûres automatiquement</Label>
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
          {DEPTHS.map(([depth, title]) => (
            <option key={depth} value={depth}>
              {title}
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
          Pistes
        </h2>
        <p className="text-sm text-muted-foreground">
          Les traces assez sûres (confiance d’au moins 60) pour qu’un scan parte aussi d’elles, et
          qui ne sont pas encore des éléments. Les plus sûres d’abord.
        </p>
      </div>
      {leads.isPending && <Pending label="Recherche des pistes…" />}
      {leads.isError && <p role="alert">{errorMessage(leads.error)}</p>}
      {leads.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Aucune piste pour l’instant : les scans en trouveront en fouillant tes éléments.
        </p>
      )}
      {!!leads.data?.length && (
        <ul className="grid gap-2">
          {leads.data.map((lead) => (
            <LeadRow key={lead.entity.id} profileId={profileId} lead={lead} />
          ))}
        </ul>
      )}
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
          Confiance {points(entity.confidence ?? 0)} · risque {RISK_LEVEL_LABELS[riskLevel(risk)]} (
          {points(risk)})
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
                onSuccess: () =>
                  toast.success(
                    'Ajouté aux éléments du profil : lance un scan pour fouiller à partir de lui.',
                  ),
                onError: (error) => toast.error(errorMessage(error)),
              },
            )
          }
        >
          <PlusIcon aria-hidden />
          Ajouter comme élément
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={dismiss.isPending}
          aria-label={`Écarter la piste ${entity.display}`}
          onClick={() => dismiss.mutate(entity.id)}
        >
          <XIcon aria-hidden />
          Écarter
        </Button>
      </div>
    </li>
  );
}
