import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { messageFor } from '@/lib/errors';
import { KIND_LABELS } from '@/lib/labels';
import { useModules, useRetryRun } from '@/lib/queries';
import { formatDuration, remainingSeconds, secondsUntil } from '@/lib/time';
import type { Run } from '@/lib/types';
import { RotateCcwIcon } from 'lucide-react';
import { RunStatusBadge } from './status';

/** One module working on one element: state, progress, results, and what to do if it fails. */
export function RunRow({ run, now }: { run: Run; now: number }) {
  const modules = useModules();
  const retry = useRetryRun();
  const title = modules.data?.find((m) => m.name === run.module)?.title ?? run.module;
  const percent =
    run.progress_total && run.progress_done !== null
      ? Math.round((100 * run.progress_done) / run.progress_total)
      : null;
  const eta = remainingSeconds(run, now);

  return (
    <li className="grid gap-1.5 py-2.5" data-testid="run" data-status={run.status}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 text-sm">
          <span className="font-medium">{title}</span>
          <span className="text-muted-foreground">
            {' · '}
            {KIND_LABELS[run.input_kind]} « {run.input_value} »
          </span>
        </div>
        <RunStatusBadge status={run.status} />
      </div>
      {percent !== null && run.status !== 'done' && (
        <Progress value={percent} aria-label={`Progression : ${percent} %`} />
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>
          {run.results_count} résultat{run.results_count > 1 ? 's' : ''}
        </span>
        {eta !== null && <span>reste ≈ {formatDuration(eta)}</span>}
        {run.status === 'rate_limited' && run.retry_at && (
          <span>reprise dans {formatDuration(secondsUntil(run.retry_at, now))}</span>
        )}
        {run.status === 'queued' && run.retry_at && (
          <span>nouvel essai dans {formatDuration(secondsUntil(run.retry_at, now))}</span>
        )}
        {run.attempts > 1 && <span>essai {run.attempts}</span>}
      </div>
      {run.error_code && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p
            className={
              run.status === 'failed'
                ? 'text-sm text-red-700 dark:text-red-300'
                : 'text-xs text-muted-foreground'
            }
          >
            {messageFor(run.error_code, run.error_params ?? {})}
          </p>
          {run.status === 'failed' && run.retryable && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => retry.mutate({ scanId: run.scan_id, runId: run.id })}
            >
              <RotateCcwIcon aria-hidden />
              Réessayer
            </Button>
          )}
        </div>
      )}
    </li>
  );
}
