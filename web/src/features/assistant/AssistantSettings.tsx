import { lazy, num, t } from '@/i18n';
import { Pending } from '@/components/Pending';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { MODEL_LABELS, PROVIDER_LABELS, PROVIDER_NAMES, pullProgress } from '@/lib/assistant';
import { messageFor } from '@/lib/errors';
import {
  useAssistant,
  useMachine,
  useModelPull,
  useStartPull,
  useTryAssistant,
  useUpdatePreferences,
} from '@/lib/queries';
import type { AssistantProvider, MachineInfo, Preferences } from '@/lib/types';
import { DownloadIcon, RefreshCwIcon } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';
import { toast } from 'sonner';

const DESCRIPTIONS: Record<AssistantProvider, string> = lazy(() => t().aiSettings.descriptions);

const SELECT =
  'h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30';

const gb = (value: number) => num(value, { maximumFractionDigits: value < 10 ? 1 : 0 });

/** The optional assistant: which one, which model, the agreement a remote one needs, and a
 * neutral question to see it answers. */
export function AssistantSettings({ preferences }: { preferences: Preferences }) {
  const status = useAssistant();
  const update = useUpdatePreferences();
  const tryIt = useTryAssistant();
  // Ticked at once; back to what is saved if saving fails.
  const [chosen, setChosen] = useState(preferences.llm_provider);
  const choose = (provider: AssistantProvider) => {
    setChosen(provider);
    update.mutate(
      { llm_provider: provider },
      { onError: () => setChosen(preferences.llm_provider) },
    );
  };
  const providers = status.data?.providers ?? ['none'];
  const remote = status.data?.provider === chosen && status.data.remote;
  return (
    <section aria-labelledby="assistant-title" className="grid gap-3">
      <div>
        <h2 id="assistant-title" className="font-heading text-lg font-semibold">
          {t().aiSettings.title}
        </h2>
        <p className="text-sm text-muted-foreground">{t().aiSettings.intro}</p>
      </div>
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">{t().aiSettings.assistant}</legend>
        {providers.map((provider) => (
          <Label key={provider} className="flex items-start gap-2 font-normal">
            <input
              type="radio"
              name="llm-provider"
              value={provider}
              checked={chosen === provider}
              onChange={() => choose(provider)}
              className="mt-0.5 size-4 accent-primary"
            />
            <span>
              {PROVIDER_LABELS[provider]}
              <span className="block text-muted-foreground">{DESCRIPTIONS[provider]}</span>
            </span>
          </Label>
        ))}
      </fieldset>
      {chosen === 'claude_code' && <ClaudeCodeModel preferences={preferences} />}
      {chosen === 'local' && <LocalModel preferences={preferences} />}
      {chosen === 'openai' && <Service preferences={preferences} />}
      {remote && <RemoteConsent provider={chosen} preferences={preferences} />}
      {chosen !== 'none' && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={
              tryIt.isPending || !status.data?.available || (remote && !preferences.llm_remote_ok)
            }
            onClick={() =>
              tryIt.mutate(undefined, {
                onSuccess: ({ model }) =>
                  toast.success(t().aiSettings.answers(PROVIDER_NAMES[chosen], model)),
              })
            }
          >
            {t().aiSettings.try}
          </Button>
          <AssistantState />
        </div>
      )}
    </section>
  );
}

function ClaudeCodeModel({ preferences }: { preferences: Preferences }) {
  const status = useAssistant();
  const update = useUpdatePreferences();
  const id = useId();
  return (
    <div className="grid max-w-xs gap-1.5">
      <Label htmlFor={id}>{t().aiSettings.model}</Label>
      <select
        id={id}
        value={preferences.llm_model ?? 'haiku'}
        onChange={(e) => update.mutate({ llm_model: e.target.value })}
        className={SELECT}
      >
        {(status.data?.models.length ? status.data.models : ['haiku']).map((model) => (
          <option key={model} value={model}>
            {MODEL_LABELS[model] ?? model}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Where what is asked goes, and the user's agreement to it. */
function RemoteConsent({
  provider,
  preferences,
}: {
  provider: AssistantProvider;
  preferences: Preferences;
}) {
  const update = useUpdatePreferences();
  const where =
    provider === 'claude_code'
      ? t().aiSettings.toAnthropic
      : t().aiSettings.toHost(preferences.llm_url ? new URL(preferences.llm_url).host : null);
  return (
    <div
      role="note"
      className="grid gap-2 rounded-md border border-amber-600/40 bg-amber-500/10 p-3 text-sm"
    >
      <p>{t().aiSettings.consentText(where)}</p>
      <Label className="flex items-start gap-2 font-normal">
        <Checkbox
          checked={preferences.llm_remote_ok}
          onCheckedChange={(checked) => update.mutate({ llm_remote_ok: checked === true })}
        />
        <span>{t().aiSettings.consent(where)}</span>
      </Label>
    </div>
  );
}

function machineText(machine: MachineInfo): string {
  const say = t().aiSettings;
  const parts = [];
  if (machine.memory_gb) parts.push(say.memory(gb(machine.memory_gb)));
  if (machine.cores) parts.push(say.cores(machine.cores));
  for (const gpu of machine.gpus)
    parts.push(
      gpu.dedicated
        ? `${gpu.name}${gpu.memory_gb ? ` (${say.gigabytes(gb(gpu.memory_gb))})` : ''}`
        : `${gpu.name} (${say.shared})`,
    );
  if (machine.unified) parts.push(say.unified);
  return parts.join(', ') || say.unknown;
}

/** A model server on this machine: what the machine can run, the servers found, the model. */
function LocalModel({ preferences }: { preferences: Preferences }) {
  const machine = useMachine(true);
  const status = useAssistant();
  const update = useUpdatePreferences();
  const modelId = useId();
  const current = preferences.llm_url ?? 'http://127.0.0.1:11434';
  const server = machine.data?.servers.find((s) => s.url === current);
  const models = server?.models ?? status.data?.models ?? [];
  const recommended = machine.data?.recommended;
  const ollama = machine.data?.servers.find((s) => s.name === 'Ollama');
  return (
    <div className="grid gap-3 rounded-md border p-3 text-sm" data-testid="local-model">
      {machine.isPending && <Pending label={t().aiSettings.readingMachine} />}
      {machine.data && recommended && (
        <>
          <p>
            {t().aiSettings.yourMachine(machineText(machine.data))}{' '}
            <strong>{recommended.model}</strong>{' '}
            {t().aiSettings.toDownload(
              gb(recommended.size_gb),
              t().aiSettings.speeds[recommended.speed],
            )}
          </p>
          {machine.data.servers.length ? (
            <ul className="grid gap-1">
              {machine.data.servers.map((found) => (
                <li key={found.url} className="flex flex-wrap items-center gap-2">
                  <span>
                    {t().aiSettings.answersOn(found.name)} <code>{found.url}</code> (
                    {t().aiSettings.models(found.models.length)})
                  </span>
                  {found.url !== current && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => update.mutate({ llm_url: found.url, llm_model: null })}
                    >
                      {t().aiSettings.use(found.name)}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p>
              {t().aiSettings.noServer}{' '}
              <a
                href="https://ollama.com/download"
                target="_blank"
                rel="noreferrer noopener"
                className="underline underline-offset-2"
              >
                Ollama
              </a>{' '}
              {t().aiSettings.noServerAfter}
            </p>
          )}
          <div>
            <Button
              size="sm"
              variant="ghost"
              disabled={machine.isFetching}
              onClick={() => void machine.refetch()}
            >
              <RefreshCwIcon aria-hidden />
              {t().aiSettings.searchAgain}
            </Button>
          </div>
          {ollama && !ollama.models.includes(recommended.model) && (
            <DownloadModel model={recommended.model} size={recommended.size_gb} />
          )}
        </>
      )}
      {models.length > 0 && (
        <div className="grid max-w-xs gap-1.5">
          <Label htmlFor={modelId}>{t().aiSettings.model}</Label>
          <select
            id={modelId}
            value={preferences.llm_model ?? ''}
            onChange={(e) => update.mutate({ llm_model: e.target.value })}
            className={SELECT}
          >
            <option value="" disabled>
              {t().aiSettings.chooseModel}
            </option>
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
                {model === recommended?.model ? ` (${t().aiSettings.recommended})` : ''}
              </option>
            ))}
          </select>
        </div>
      )}
      <Address preferences={preferences} placeholder="http://127.0.0.1:11434" />
    </div>
  );
}

/** Has Ollama download the recommended model, once the user saw its size. */
function DownloadModel({ model, size }: { model: string; size: number }) {
  const pull = useModelPull();
  const start = useStartPull();
  if (pull.data?.status === 'pulling')
    return (
      <p role="status">
        {t().aiSettings.downloading(
          String(pull.data.model),
          pullProgress(pull.data.completed, pull.data.total),
        )}
      </p>
    );
  return (
    <div className="grid gap-1">
      {pull.data?.status === 'failed' && (
        <p role="alert">{messageFor(pull.data.error_code ?? 'pull_failed')}</p>
      )}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button size="sm" className="w-fit">
            <DownloadIcon aria-hidden />
            {t().aiSettings.download(model, gb(size))}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t().aiSettings.downloadTitle(model)}</AlertDialogTitle>
            <AlertDialogDescription>{t().aiSettings.downloadText(gb(size))}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t().common.cancel}</AlertDialogCancel>
            <AlertDialogAction onClick={() => start.mutate(model)}>
              {t().aiSettings.downloadGo}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function Address({ preferences, placeholder }: { preferences: Preferences; placeholder: string }) {
  const update = useUpdatePreferences();
  const id = useId();
  const [value, setValue] = useState(preferences.llm_url ?? '');
  const save = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      { llm_url: value.trim() || null },
      { onSuccess: (saved) => setValue(saved.llm_url ?? '') },
    );
  };
  return (
    <form onSubmit={save} className="flex flex-wrap items-end gap-2">
      <div className="grid min-w-64 flex-1 gap-1.5">
        <Label htmlFor={id}>{t().aiSettings.address}</Label>
        <Input
          id={id}
          type="url"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
        />
      </div>
      <Button
        type="submit"
        variant="outline"
        disabled={update.isPending || value.trim() === (preferences.llm_url ?? '')}
      >
        {t().common.save}
      </Button>
    </form>
  );
}

/** Any OpenAI-compatible service: its address, model and key. */
function Service({ preferences }: { preferences: Preferences }) {
  const update = useUpdatePreferences();
  const modelId = useId();
  const keyId = useId();
  const [model, setModel] = useState(preferences.llm_model ?? '');
  const [key, setKey] = useState('');
  return (
    <div className="grid gap-3 rounded-md border p-3 text-sm">
      <Address preferences={preferences} placeholder="https://llm.example.org" />
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate({ llm_model: model.trim() || null });
        }}
      >
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor={modelId}>{t().aiSettings.model}</Label>
          <Input
            id={modelId}
            spellCheck={false}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={t().aiSettings.modelHint}
          />
        </div>
        <Button
          type="submit"
          variant="outline"
          disabled={update.isPending || model.trim() === (preferences.llm_model ?? '')}
        >
          {t().common.save}
        </Button>
      </form>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate({ llm_key: key }, { onSuccess: () => setKey('') });
        }}
      >
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor={keyId}>
            {preferences.llm_key_set ? t().aiSettings.replaceKey : t().aiSettings.key}
          </Label>
          <Input
            id={keyId}
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        </div>
        <Button type="submit" variant="outline" disabled={!key.trim() || update.isPending}>
          {t().common.save}
        </Button>
        {preferences.llm_key_set && (
          <Button type="button" variant="ghost" onClick={() => update.mutate({ llm_key: null })}>
            {t().aiSettings.removeKey}
          </Button>
        )}
      </form>
    </div>
  );
}

function AssistantState() {
  const status = useAssistant();
  if (status.isPending) return <Pending label={t().aiSettings.checking} />;
  if (!status.data) return null;
  const name = PROVIDER_NAMES[status.data.provider];
  return (
    <p className="text-sm" role="status" data-testid="assistant-state">
      {status.data.available ? (
        t().aiSettings.ready(name)
      ) : (
        <>
          {messageFor(status.data.reason ?? 'llm_failed')}
          {status.data.reason === 'llm_missing' && (
            <>
              {' '}
              <a
                href="https://claude.com/claude-code"
                target="_blank"
                rel="noreferrer noopener"
                className="underline underline-offset-2"
              >
                {t().aiSettings.installClaude}
              </a>
            </>
          )}
        </>
      )}
    </p>
  );
}
