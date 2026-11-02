import { Button } from '@/components/ui/button';
import { t } from '@/i18n';
import { useInfo, useUpdatePreferences } from '@/lib/queries';
import { useSwitchSide } from '@/lib/side';
import { errorMessage } from '@/lib/errors';

/** What someone sees the first time: what Narcisse is for, who it may look for, what leaves the
 * machine. Then their own data, or the demo to try it first. */
export function Welcome() {
  const update = useUpdatePreferences();
  const info = useInfo();
  const side = useSwitchSide();
  const texts = t().welcome;
  return (
    <div className="mx-auto grid max-w-2xl gap-6" data-testid="welcome">
      <div className="grid gap-2">
        <h1 className="font-heading text-2xl font-semibold">{texts.title}</h1>
        <p className="text-muted-foreground">{texts.intro}</p>
      </div>
      {texts.sections.map(([title, body]) => (
        <section key={title} className="grid gap-1">
          <h2 className="font-heading text-lg font-semibold">{title}</h2>
          <p className="text-sm">{body}</p>
        </section>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={update.isPending || side.isPending}
          onClick={() => update.mutate({ welcomed: true })}
        >
          {texts.start}
        </Button>
        {info.data?.can_switch && (
          <Button
            variant="outline"
            disabled={update.isPending || side.isPending}
            onClick={() => side.mutate()}
          >
            {side.isPending ? t().shell.switching : texts.tryIt}
          </Button>
        )}
      </div>
      {side.isError && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {errorMessage(side.error)}
        </p>
      )}
      {info.data?.can_switch && <p className="text-sm text-muted-foreground">{texts.tryHint}</p>}
    </div>
  );
}
