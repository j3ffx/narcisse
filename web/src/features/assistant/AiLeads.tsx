import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS } from '@/lib/labels';
import { useAddSeed, useAiLeads, useDismissAiLead } from '@/lib/queries';
import type { AiLead } from '@/lib/types';
import { PlusIcon, XIcon } from 'lucide-react';
import { useId } from 'react';
import { toast } from 'sonner';
import { Link } from 'wouter';

/** The elements the assistant read in the traces' proofs. They are not traces: nothing follows
 * them until the user adds one as an element. */
export function AiLeads({ profileId }: { profileId: number }) {
  const leads = useAiLeads(profileId, true);
  const id = useId();
  if (!leads.data?.length) return null;
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-2">
      <h3 id={`${id}-title`} className="flex items-center gap-2 font-semibold">
        Suggérées par l’IA <Badge variant="secondary">Avis de l’IA</Badge>
      </h3>
      <p className="text-sm text-muted-foreground">
        Relevées par l’assistant dans les preuves d’une trace, telles qu’elles y sont écrites. Rien
        ne part d’elles tant que tu ne les ajoutes pas comme éléments.
      </p>
      <ul className="grid gap-2">
        {leads.data.map((lead) => (
          <AiLeadRow
            key={`${lead.annotation_id}-${lead.index}`}
            profileId={profileId}
            lead={lead}
          />
        ))}
      </ul>
    </section>
  );
}

function AiLeadRow({ profileId, lead }: { profileId: number; lead: AiLead }) {
  const add = useAddSeed(profileId);
  const dismiss = useDismissAiLead(profileId);
  return (
    <li
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed p-3"
      data-testid="ai-lead"
    >
      <div className="grid min-w-0 gap-0.5">
        <p className="flex min-w-0 items-baseline gap-2">
          <span className="shrink-0 text-xs text-muted-foreground">{KIND_LABELS[lead.kind]}</span>
          <span className="truncate font-medium">{lead.value}</span>
        </p>
        <p className="text-xs text-muted-foreground">
          {lead.reason} Vue dans{' '}
          <Link
            href={`/profils/${profileId}?trace=${lead.source.id}`}
            className="underline underline-offset-2"
          >
            {lead.source.display}
          </Link>
          .
        </p>
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={add.isPending}
          onClick={() =>
            add.mutate(
              { kind: lead.kind, value: lead.value },
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
          aria-label={`Écarter la piste ${lead.value}`}
          onClick={() => dismiss.mutate(lead)}
        >
          <XIcon aria-hidden />
          Écarter
        </Button>
      </div>
    </li>
  );
}
