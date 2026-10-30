import { t } from '@/i18n';
import { Button } from '@/components/ui/button';
import { useSearxng, useStartSearxng } from '@/lib/queries';
import { launchState } from '@/lib/searxng';
import { Loader2Icon, PlayIcon } from 'lucide-react';
import { useId } from 'react';

/** The user's SearXNG is set but doesn't answer (stopped with the machine, most often): say so
 * where the web search is about to be used, and offer to start it again. */
export function SearxngDown() {
  const status = useSearxng();
  const launch = useStartSearxng();
  const id = useId();
  const data = status.data;
  if (!data?.address || (data.running && data.state !== 'ready')) return null;
  const starting = data.state === 'starting';
  if (data.running) {
    return (
      <p className="text-sm" role="status">
        {t().searxng.backUp}
      </p>
    );
  }
  return (
    <div className="grid gap-1.5 text-sm" data-testid="searxng-down">
      <p>{t().searxng.down}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => launch.mutate()}
          disabled={starting || launch.isPending}
          aria-describedby={`${id}-state`}
        >
          {starting ? (
            <Loader2Icon aria-hidden className="animate-spin" />
          ) : (
            <PlayIcon aria-hidden />
          )}
          {t().searxng.restart}
        </Button>
        <span id={`${id}-state`} className="text-muted-foreground" role="status">
          {launchState(data)}
        </span>
      </div>
    </div>
  );
}
