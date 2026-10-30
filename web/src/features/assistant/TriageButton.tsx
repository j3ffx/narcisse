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
import { PROVIDER_LABELS } from '@/lib/assistant';
import { useAssistant, useTriage, useTriageCount } from '@/lib/queries';
import { SparklesIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

/** Asks the assistant "is it me?" about the profile's traces waiting for a review, one batch at
 * a time, after saying how many questions that makes. */
export function TriageButton({ profileId }: { profileId: number }) {
  const status = useAssistant();
  const [open, setOpen] = useState(false);
  const count = useTriageCount(profileId, open);
  const triage = useTriage(profileId);
  if (!status.data || status.data.provider === 'none') return null;
  const name = PROVIDER_LABELS[status.data.provider];
  const blocked = status.data.remote && !status.data.remote_ok;
  const waiting = count.data?.count ?? 0;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <SparklesIcon aria-hidden />
          Trier avec l’IA
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Trier les traces à vérifier</DialogTitle>
          <DialogDescription>
            {name} dit, pour chaque trace pas encore triée, si c’est sans doute toi. Rien n’est
            appliqué : chaque avis attend ton clic dans le détail de la trace.
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm" role="status" data-testid="triage-count">
          {blocked
            ? `${name} envoie les traces hors de ta machine : autorise-le d’abord dans les Réglages.`
            : count.isPending
              ? 'Calcul du nombre de traces…'
              : waiting === 0
                ? 'Aucune trace à trier : elles sont toutes triées, ou déjà demandées.'
                : `${waiting} question${waiting > 1 ? 's' : ''}, une par trace${
                    count.data?.capped ? ' (les suivantes au prochain lot)' : ''
                  }${status.data.remote ? ', chacune envoyée à Anthropic' : ''}.`}
        </p>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Annuler
          </Button>
          <Button
            disabled={blocked || waiting === 0 || triage.isPending}
            onClick={() =>
              triage.mutate(undefined, {
                onSuccess: (done) => {
                  setOpen(false);
                  toast.success(
                    `${done.count} question${done.count > 1 ? 's' : ''} envoyée${done.count > 1 ? 's' : ''} à ${name}. Les avis arrivent dans le détail des traces.`,
                  );
                },
              })
            }
          >
            Lancer le tri
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
