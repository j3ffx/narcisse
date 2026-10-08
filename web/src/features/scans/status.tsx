import { Badge } from '@/components/ui/badge';
import { RUN_STATUS_LABELS, SCAN_STATUS_LABELS } from '@/lib/labels';
import type { RunStatus, ScanStatus } from '@/lib/types';
import { cn } from 'cn';
import {
  CheckIcon,
  CircleSlashIcon,
  ClockIcon,
  HourglassIcon,
  LoaderIcon,
  PauseIcon,
  TriangleAlertIcon,
  type LucideIcon,
} from 'lucide-react';

const STYLES: Record<RunStatus, { icon: LucideIcon; className: string }> = {
  queued: { icon: ClockIcon, className: 'bg-muted text-muted-foreground' },
  running: {
    icon: LoaderIcon,
    className: 'bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-100',
  },
  paused: {
    icon: PauseIcon,
    className: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100',
  },
  rate_limited: {
    icon: HourglassIcon,
    className: 'bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-100',
  },
  failed: {
    icon: TriangleAlertIcon,
    className: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-100',
  },
  done: {
    icon: CheckIcon,
    className: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100',
  },
  cancelled: { icon: CircleSlashIcon, className: 'bg-muted text-muted-foreground' },
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { icon: Icon, className } = STYLES[status];
  return (
    <Badge className={cn('gap-1', className)}>
      <Icon
        aria-hidden
        className={cn(status === 'running' && 'motion-safe:animate-spin [animation-duration:2s]')}
      />
      {RUN_STATUS_LABELS[status]}
    </Badge>
  );
}

export function ScanStatusBadge({ status }: { status: ScanStatus }) {
  const { icon: Icon, className } = STYLES[status];
  return (
    <Badge className={cn('gap-1', className)}>
      <Icon
        aria-hidden
        className={cn(status === 'running' && 'motion-safe:animate-spin [animation-duration:2s]')}
      />
      {SCAN_STATUS_LABELS[status]}
    </Badge>
  );
}
