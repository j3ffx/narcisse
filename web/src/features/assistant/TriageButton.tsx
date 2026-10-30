import { t } from '@/i18n';
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
          {t().triage.button}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t().triage.title}</DialogTitle>
          <DialogDescription>{t().triage.intro(name)}</DialogDescription>
        </DialogHeader>
        <p className="text-sm" role="status" data-testid="triage-count">
          {blocked
            ? t().triage.blocked(name)
            : count.isPending
              ? t().triage.counting
              : waiting === 0
                ? t().triage.none
                : t().triage.questions(waiting, count.data?.capped ?? false, status.data.remote)}
        </p>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            {t().common.cancel}
          </Button>
          <Button
            disabled={blocked || waiting === 0 || triage.isPending}
            onClick={() =>
              triage.mutate(undefined, {
                onSuccess: (done) => {
                  setOpen(false);
                  toast.success(t().triage.sent(done.count, name));
                },
              })
            }
          >
            {t().triage.start}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
