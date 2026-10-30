import { t } from '@/i18n';
import { Button } from '@/components/ui/button';
import { errorMessage } from '@/lib/errors';
import { SEED_KINDS } from '@/lib/labels';
import { useAddSeed, useProfile } from '@/lib/queries';
import type { GraphNode, SeedKind } from '@/lib/types';
import { PlusIcon } from 'lucide-react';
import { toast } from 'sonner';

const isSeedKind = (kind: string): kind is SeedKind => SEED_KINDS.includes(kind as SeedKind);

/** Makes a trace one of the profile's elements, so that the next scans search from it too. */
export function AddAsSeed({ profileId, entity }: { profileId: number; entity: GraphNode }) {
  const profile = useProfile(profileId);
  const add = useAddSeed(profileId);
  const kind = entity.kind;
  if (!isSeedKind(kind) || entity.modules.includes('seed') || entity.status === 'false_positive')
    return null;
  const added = profile.data?.seeds.some(
    (seed) => seed.kind === kind && seed.normalized === entity.normalized,
  );
  if (added) return <p className="text-sm text-muted-foreground">{t().seeds.isElement}</p>;
  return (
    <Button
      size="sm"
      variant="outline"
      className="w-fit"
      disabled={add.isPending || profile.isPending}
      onClick={() =>
        add.mutate(
          { kind, value: entity.display },
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
  );
}
