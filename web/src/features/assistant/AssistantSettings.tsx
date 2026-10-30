import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { MODEL_LABELS, PROVIDER_LABELS } from '@/lib/assistant';
import { messageFor } from '@/lib/errors';
import { useAssistant, useTryAssistant, useUpdatePreferences } from '@/lib/queries';
import type { AssistantProvider, Preferences } from '@/lib/types';
import { useId, useState } from 'react';
import { toast } from 'sonner';

const DESCRIPTIONS: Record<AssistantProvider, string> = {
  none: 'Rien n’est jamais envoyé à une IA.',
  claude_code: 'Ton Claude Code, avec ton abonnement. Ce que tu lui demandes part chez Anthropic.',
  demo: 'Des réponses fictives, pour essayer : rien n’est envoyé.',
};

/** The optional assistant: which one, which model, the agreement a remote one needs, and a
 * neutral question to see it answers. */
export function AssistantSettings({ preferences }: { preferences: Preferences }) {
  const status = useAssistant();
  const update = useUpdatePreferences();
  const tryIt = useTryAssistant();
  const modelId = useId();
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
  const remote = status.data?.remote ?? false;
  return (
    <section aria-labelledby="assistant-title" className="grid gap-3">
      <div>
        <h2 id="assistant-title" className="font-heading text-lg font-semibold">
          Assistant IA (facultatif)
        </h2>
        <p className="text-sm text-muted-foreground">
          Narcisse marche sans IA. Un assistant peut t’aider à trier les traces (« est-ce bien moi ?
          ») et à les comprendre. Il ne lit une trace que quand tu lui poses la question, ses
          réponses sont marquées « Avis de l’IA », et rien n’est appliqué sans ton clic.
        </p>
      </div>
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">Assistant</legend>
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
      {chosen === 'claude_code' && (
        <>
          <div className="grid max-w-xs gap-1.5">
            <Label htmlFor={modelId}>Modèle</Label>
            <select
              id={modelId}
              value={preferences.llm_model ?? 'haiku'}
              onChange={(e) => update.mutate({ llm_model: e.target.value })}
              className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            >
              {(status.data?.models.length ? status.data.models : ['haiku']).map((model) => (
                <option key={model} value={model}>
                  {MODEL_LABELS[model] ?? model}
                </option>
              ))}
            </select>
          </div>
          <div
            role="note"
            className="grid gap-2 rounded-md border border-amber-600/40 bg-amber-500/10 p-3 text-sm"
          >
            <p>
              Avec Claude Code, chaque question envoie à Anthropic la trace, ses preuves, et les
              noms et pseudos que tu as déclarés, rien d’autre. Le texte exact est visible avant
              chaque envoi (« Voir ce qui part »).
            </p>
            <Label className="flex items-start gap-2 font-normal">
              <Checkbox
                checked={preferences.llm_remote_ok}
                onCheckedChange={(checked) => update.mutate({ llm_remote_ok: checked === true })}
              />
              <span>
                J’accepte que ces données partent chez Anthropic quand je pose une question.
              </span>
            </Label>
          </div>
        </>
      )}
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
                  toast.success(`${PROVIDER_LABELS[chosen]} répond${model ? ` (${model})` : ''}.`),
              })
            }
          >
            Essayer
          </Button>
          <AssistantState />
        </div>
      )}
    </section>
  );
}

function AssistantState() {
  const status = useAssistant();
  if (status.isPending) return <Pending label="Vérification de l’assistant…" />;
  if (!status.data) return null;
  const name = PROVIDER_LABELS[status.data.provider];
  return (
    <p className="text-sm" role="status" data-testid="assistant-state">
      {status.data.available ? (
        `${name} est prêt.`
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
                Installer Claude Code
              </a>
            </>
          )}
        </>
      )}
    </p>
  );
}
