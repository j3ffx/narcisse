import { Pending } from '@/components/Pending';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PROVIDER_NAMES, answeredBy, isBusy, latest, stateText, textOf } from '@/lib/assistant';
import { messageFor } from '@/lib/errors';
import {
  useAdaptLetter,
  useAnnotations,
  useAssistant,
  useLetterPrompt,
  useUpdateAnnotation,
} from '@/lib/queries';
import type { LetterRequest } from '@/lib/types';
import { SparklesIcon } from 'lucide-react';
import { useId, useState } from 'react';

/** "Adapt with the AI" in a letter's dialog: a sentence of context and a tone, the text sent
 * (the profile's identity behind markers), then a proposal the user takes or leaves. */
export function LetterAssistant({
  entityId,
  subject,
  body,
  onTake,
  onRestore,
}: {
  entityId: number;
  subject: string;
  body: string;
  onTake: (subject: string, body: string) => void;
  onRestore: () => void;
}) {
  const status = useAssistant();
  const on = status.data !== undefined && status.data.provider !== 'none';
  const annotations = useAnnotations(entityId, on);
  const adapt = useAdaptLetter(entityId);
  const preview = useLetterPrompt(entityId);
  const update = useUpdateAnnotation();
  const id = useId();
  const [context, setContext] = useState('');
  const [tone, setTone] = useState<LetterRequest['tone']>('courteous');
  if (!status.data || !on) return null;
  const blocked = status.data.remote && !status.data.remote_ok;
  const proposal = latest(annotations.data ?? [], 'letter');
  const request: LetterRequest = { subject, body, context: context.trim() || null, tone };
  return (
    <details
      className="grid gap-2 rounded-md border border-dashed p-2 text-sm"
      data-testid="letter-assistant"
    >
      <summary className="flex w-fit cursor-pointer items-center gap-1.5 font-medium">
        <SparklesIcon aria-hidden className="size-4" />
        Adapter avec l’IA
      </summary>
      {blocked ? (
        <p className="mt-2 text-muted-foreground">
          {PROVIDER_NAMES[status.data.provider]} envoie la lettre hors de ta machine : autorise-le
          d’abord dans les Réglages.
        </p>
      ) : (
        <div className="mt-2 grid gap-2">
          <div className="grid gap-1">
            <Label htmlFor={`${id}-context`}>Ce que tu veux ajouter (facultatif)</Label>
            <Input
              id={`${id}-context`}
              value={context}
              maxLength={500}
              placeholder="compte ouvert en 2012, plus utilisé depuis"
              onChange={(e) => setContext(e.target.value)}
            />
          </div>
          <fieldset className="flex flex-wrap gap-3">
            <legend className="sr-only">Ton de la lettre</legend>
            {(
              [
                ['courteous', 'Courtois'],
                ['firm', 'Ferme'],
              ] as const
            ).map(([value, label]) => (
              <Label key={value} className="flex items-center gap-1.5 font-normal">
                <input
                  type="radio"
                  name={`${id}-tone`}
                  checked={tone === value}
                  onChange={() => setTone(value)}
                  className="size-4 accent-primary"
                />
                {label}
              </Label>
            ))}
          </fieldset>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={adapt.isPending || isBusy(proposal) || !body.trim()}
              onClick={() => adapt.mutate(request)}
            >
              Adapter
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={preview.isPending}
              onClick={() => preview.mutate(request)}
            >
              Voir ce qui part
            </Button>
          </div>
          {preview.data && (
            <pre
              tabIndex={0}
              aria-label="Texte envoyé à l’assistant"
              className="max-h-48 overflow-auto rounded-md border bg-muted/40 p-2 text-xs whitespace-pre-wrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              data-testid="letter-prompt"
            >
              {preview.data.text}
            </pre>
          )}
        </div>
      )}
      {proposal && proposal.decision !== 'dismissed' && (
        <div className="mt-2 grid gap-1.5" data-testid="letter-proposal">
          <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <Badge variant="secondary">Avis de l’IA</Badge>
            Proposition · {answeredBy(proposal)}
          </p>
          {isBusy(proposal) && (
            <p role="status" className="text-muted-foreground">
              {stateText(proposal, PROVIDER_NAMES[proposal.provider])}
            </p>
          )}
          {proposal.state === 'failed' && (
            <p role="alert">
              {messageFor(proposal.error_code ?? 'llm_failed', proposal.error_params ?? {})}
            </p>
          )}
          {proposal.state === 'done' && (
            <>
              <pre
                tabIndex={0}
                aria-label="Lettre proposée"
                className="max-h-64 overflow-auto rounded-md border p-2 text-xs whitespace-pre-wrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                {textOf(proposal, 'subject')}
                {'\n\n'}
                {textOf(proposal, 'body')}
              </pre>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    onTake(textOf(proposal, 'subject'), textOf(proposal, 'body'));
                    update.mutate({ id: proposal.id, decision: 'accepted' });
                  }}
                >
                  Reprendre ce texte
                </Button>
                <Button size="sm" variant="ghost" onClick={onRestore}>
                  Revenir au modèle
                </Button>
              </div>
            </>
          )}
        </div>
      )}
      {annotations.isPending && <Pending label="Chargement…" />}
    </details>
  );
}
