import { t } from '@/i18n';
import { Pending } from '@/components/Pending';
import { AssistantSettings } from '@/features/assistant/AssistantSettings';
import { Backups } from './Backups';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { launchState } from '@/lib/searxng';
import {
  useInfo,
  usePreferences,
  useSearxng,
  useStartSearxng,
  useUpdatePreferences,
} from '@/lib/queries';
import { Loader2Icon, PlayIcon, XIcon } from 'lucide-react';
import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { toast } from 'sonner';

export function SettingsPage() {
  const preferences = usePreferences();
  const info = useInfo();
  return (
    <div className="grid max-w-2xl gap-8">
      <div>
        <h1 className="font-heading text-2xl font-semibold">{t().shell.settings}</h1>
        <p className="text-sm text-muted-foreground">{t().settings.intro(info.data?.data_dir)}</p>
      </div>
      {preferences.isPending && <Pending label={t().settings.loading} />}
      {preferences.isError && <p role="alert">{errorMessage(preferences.error)}</p>}
      {preferences.data && (
        <>
          <Language choice={preferences.data.ui_lang} />
          <Token
            service="github"
            title={t().settings.githubTitle}
            saved={preferences.data.github_token_set}
            placeholder="github_pat_…"
          >
            {t().settings.githubHelp}
          </Token>
          <Token
            service="gitlab"
            title={t().settings.gitlabTitle}
            saved={preferences.data.gitlab_token_set}
            placeholder="glpat-…"
          >
            {t().settings.gitlabHelp}
          </Token>
          <FediverseInstances instances={preferences.data.fediverse_instances} />
          <SearxngInstance
            address={preferences.data.searxng_url}
            autostart={preferences.data.searxng_autostart}
          />
          <AdultSites excluded={preferences.data.exclude_adult} />
          <AssistantSettings preferences={preferences.data} />
          <Backups />
        </>
      )}
    </div>
  );
}

const SERVICE_NAMES = { github: 'GitHub', gitlab: 'GitLab' } as const;

const LANGUAGES = ['auto', 'fr', 'en'] as const;

/** The language of Narcisse: the browser's, or the one chosen. */
function Language({ choice }: { choice: (typeof LANGUAGES)[number] }) {
  const update = useUpdatePreferences();
  const id = useId();
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-3">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          {t().settings.languageTitle}
        </h2>
        <p className="text-sm text-muted-foreground">{t().settings.languageHelp}</p>
      </div>
      <div className="grid w-fit gap-1.5">
        <Label htmlFor={`${id}-lang`}>{t().settings.language}</Label>
        <select
          id={`${id}-lang`}
          className="h-8 rounded-lg border bg-background px-2 text-sm"
          value={choice}
          disabled={update.isPending}
          onChange={(e) => update.mutate({ ui_lang: e.target.value as (typeof LANGUAGES)[number] })}
        >
          {LANGUAGES.map((value) => (
            <option key={value} value={value} lang={value === 'auto' ? undefined : value}>
              {value === 'auto' ? t().settings.auto : value === 'fr' ? 'Français' : 'English'}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}

function Token({
  service,
  title,
  saved,
  placeholder,
  children,
}: {
  service: keyof typeof SERVICE_NAMES;
  title: string;
  saved: boolean;
  placeholder: string;
  children: ReactNode;
}) {
  const [token, setToken] = useState('');
  const update = useUpdatePreferences();
  const key = `${service}_token` as const;
  const name = SERVICE_NAMES[service];
  const save = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      { [key]: token },
      {
        onSuccess: () => {
          setToken('');
          toast.success(t().settings.tokenSaved(name));
        },
      },
    );
  };
  return (
    <section aria-labelledby={`${service}-title`} className="grid gap-3">
      <div>
        <h2 id={`${service}-title`} className="font-heading text-lg font-semibold">
          {title}
        </h2>
        <p className="text-sm text-muted-foreground">{children}</p>
      </div>
      <p className="text-sm" data-testid={`${service}-token-state`}>
        {saved ? t().settings.tokenSet : t().settings.noToken}
      </p>
      <form onSubmit={save} className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor={`${service}-token`}>
            {saved ? t().settings.replaceToken : t().settings.token}
          </Label>
          <Input
            id={`${service}-token`}
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={placeholder}
          />
        </div>
        <Button type="submit" disabled={!token.trim() || update.isPending}>
          {t().common.save}
        </Button>
        {saved && (
          <Button
            type="button"
            variant="ghost"
            onClick={() =>
              update.mutate(
                { [key]: null },
                { onSuccess: () => toast.success(t().settings.tokenRemoved(name)) },
              )
            }
          >
            {t().common.remove}
          </Button>
        )}
      </form>
    </section>
  );
}

function FediverseInstances({ instances }: { instances: string[] }) {
  const [instance, setInstance] = useState('');
  const update = useUpdatePreferences();
  const add = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      { fediverse_instances: [...instances, instance] },
      { onSuccess: () => setInstance('') },
    );
  };
  return (
    <section aria-labelledby="fediverse-title" className="grid gap-3">
      <div>
        <h2 id="fediverse-title" className="font-heading text-lg font-semibold">
          {t().settings.fediverseTitle}
        </h2>
        <p className="text-sm text-muted-foreground">{t().settings.fediverseHelp}</p>
      </div>
      {instances.length > 0 ? (
        <ul className="flex flex-wrap gap-2" aria-label={t().settings.instancesAdded}>
          {instances.map((host) => (
            <li
              key={host}
              className="flex items-center gap-1 rounded-md border py-0.5 pr-0.5 pl-2 text-sm"
            >
              {host}
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={t().seeds.remove(host)}
                disabled={update.isPending}
                onClick={() =>
                  update.mutate({ fediverse_instances: instances.filter((h) => h !== host) })
                }
              >
                <XIcon aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm">{t().settings.noInstance}</p>
      )}
      <form onSubmit={add} className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor="fediverse-instance">{t().settings.instance}</Label>
          <Input
            id="fediverse-instance"
            spellCheck={false}
            value={instance}
            onChange={(e) => setInstance(e.target.value)}
            placeholder="instance.example"
          />
        </div>
        <Button type="submit" disabled={!instance.trim() || update.isPending}>
          {t().seeds.add}
        </Button>
      </form>
    </section>
  );
}

function SearxngInstance({ address, autostart }: { address: string | null; autostart: boolean }) {
  const [value, setValue] = useState(address ?? '');
  const update = useUpdatePreferences();
  const status = useSearxng();
  const launch = useStartSearxng();
  const starting = status.data?.state === 'starting';
  const save = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      { searxng_url: value.trim() || null },
      { onSuccess: (saved) => setValue(saved.searxng_url ?? '') },
    );
  };
  return (
    <section aria-labelledby="searxng-title" className="grid gap-3">
      <div>
        <h2 id="searxng-title" className="font-heading text-lg font-semibold">
          {t().settings.searxngTitle}
        </h2>
        <p className="text-sm text-muted-foreground">{t().settings.searxngHelp}</p>
      </div>
      {status.data?.running && status.data.address && (
        <p className="text-sm" data-testid="searxng-state">
          {t().settings.searxngRunsOn}{' '}
          <code className="text-foreground">{status.data.address}</code>
          {t().settings.searxngUsed}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={() => launch.mutate()}
          disabled={starting || launch.isPending}
          aria-describedby="searxng-launch-state"
        >
          {starting ? (
            <Loader2Icon aria-hidden className="animate-spin" />
          ) : (
            <PlayIcon aria-hidden />
          )}
          {address ? t().searxng.restart : t().settings.searxngInstall}
        </Button>
        <p id="searxng-launch-state" className="text-sm text-muted-foreground" role="status">
          {launchState(status.data) ||
            (status.data && address && !status.data.running
              ? t().settings.searxngDown(address)
              : '')}
        </p>
      </div>
      {address && (
        <Label className="flex items-start gap-2 font-normal">
          <Checkbox
            checked={autostart}
            onCheckedChange={(checked) => update.mutate({ searxng_autostart: checked === true })}
          />
          <span>{t().settings.searxngAutostart}</span>
        </Label>
      )}
      <details className="text-sm">
        <summary className="w-fit cursor-pointer text-muted-foreground underline-offset-2 hover:underline">
          {t().settings.searxngManual}
        </summary>
        <form onSubmit={save} className="mt-2 flex flex-wrap items-end gap-2">
          <div className="grid min-w-64 flex-1 gap-1.5">
            <Label htmlFor="searxng-url">{t().settings.searxngAddress}</Label>
            <Input
              id="searxng-url"
              type="url"
              spellCheck={false}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="http://127.0.0.1:8888"
            />
          </div>
          <Button
            type="submit"
            variant="outline"
            disabled={update.isPending || value.trim() === (address ?? '')}
          >
            {value.trim() || !address ? t().common.save : t().common.remove}
          </Button>
        </form>
      </details>
    </section>
  );
}

function AdultSites({ excluded }: { excluded: boolean }) {
  const update = useUpdatePreferences();
  return (
    <section aria-labelledby="adult-title" className="grid gap-3">
      <h2 id="adult-title" className="font-heading text-lg font-semibold">
        {t().settings.adultTitle}
      </h2>
      <p className="text-sm text-muted-foreground">{t().settings.adultHelp}</p>
      <Label className="flex items-center gap-2 font-normal">
        <Checkbox
          checked={excluded}
          onCheckedChange={(checked) => update.mutate({ exclude_adult: checked === true })}
        />
        {t().settings.adultExclude}
      </Label>
    </section>
  );
}
