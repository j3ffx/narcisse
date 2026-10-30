import { t } from '@/i18n';
import { useScans } from '@/lib/queries';
import { formatDate } from '@/lib/time';
import type { GraphNode } from '@/lib/types';
import { useId } from 'react';

/** The graph (and the list) as one of the profile's past scans left it: the traces known then,
 * not yet gone. The last position is now. */
export function TimeSlider({
  profileId,
  nodes,
  asOf,
  onChange,
}: {
  profileId: number;
  nodes: GraphNode[];
  asOf: string | null;
  onChange: (asOf: string | null) => void;
}) {
  const id = useId();
  const scans = useScans(profileId);
  const steps = (scans.data ?? [])
    .filter((s) => s.status === 'done' && s.finished_at && !s.notes?.check)
    .map((s) => s.finished_at!)
    .sort();
  if (steps.length < 2) return null;
  const index = asOf === null ? steps.length : Math.max(0, steps.indexOf(asOf));
  const appeared =
    asOf === null
      ? 0
      : nodes.filter(
          (n) =>
            n.kind !== 'identity' &&
            n.first_seen <= asOf &&
            (index === 0 || n.first_seen > steps[index - 1]!),
        ).length;
  return (
    <div className="flex items-center gap-2 text-sm" data-testid="time-slider">
      <label htmlFor={id} className="shrink-0">
        {asOf === null ? t().slider.now : t().slider.atScan(formatDate(asOf))}
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={steps.length}
        step={1}
        value={index}
        aria-valuetext={asOf === null ? t().slider.now : t().slider.scanOf(formatDate(asOf))}
        onChange={(e) => {
          const next = Number(e.target.value);
          onChange(next >= steps.length ? null : steps[next]!);
        }}
        className="w-36 accent-primary"
      />
      {asOf !== null && (
        <span className="text-muted-foreground" role="status">
          {t().slider.appeared(appeared)}
        </span>
      )}
    </div>
  );
}
