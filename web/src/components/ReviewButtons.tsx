import { t } from '@/i18n';
import { Button } from '@/components/ui/button';
import { useReviewEntity } from '@/lib/queries';
import type { Entity, EntityStatus } from '@/lib/types';
import { CheckIcon, XIcon } from 'lucide-react';

/** "It's me" / "not me"; pressing the active one again puts the trace back to "not sure". */
export function ReviewButtons({ entity }: { entity: Entity }) {
  const review = useReviewEntity();
  const set = (status: EntityStatus) =>
    review.mutate({ entity, status: entity.status === status ? 'unreviewed' : status });
  const confirmed = entity.status === 'confirmed';
  const rejected = entity.status === 'false_positive';
  return (
    <div className="flex shrink-0 gap-1" role="group" aria-label={t().review.sort(entity.display)}>
      <Button
        size="sm"
        variant={confirmed ? 'default' : 'outline'}
        aria-pressed={confirmed}
        aria-label={t().entityStatus.confirmed}
        onClick={() => set('confirmed')}
      >
        <CheckIcon aria-hidden />
        <span className="hidden sm:inline">{t().entityStatus.confirmed}</span>
      </Button>
      <Button
        size="sm"
        variant={rejected ? 'secondary' : 'ghost'}
        aria-pressed={rejected}
        aria-label={t().entityStatus.false_positive}
        onClick={() => set('false_positive')}
      >
        <XIcon aria-hidden />
        <span className="hidden sm:inline">{t().entityStatus.false_positive}</span>
      </Button>
    </div>
  );
}
