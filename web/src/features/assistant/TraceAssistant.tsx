import { Pending } from '@/components/Pending';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  PROVIDER_LABELS,
  TASK_LABELS,
  VERDICT_LABELS,
  answeredBy,
  isBusy,
  latest,
  stateText,
  textOf,
  verdictOf,
} from '@/lib/assistant';
import { messageFor } from '@/lib/errors';
import {
  useAnnotations,
  useAsk,
  useAssistant,
  useDeleteAnnotation,
  usePrompt,
  useUpdateAnnotation,
} from '@/lib/queries';
import { formatDate } from '@/lib/time';
import type { Annotation, AnnotationTask, AssistantStatus, Entity } from '@/lib/types';
import { SparklesIcon, Trash2Icon } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';
import { Link } from 'wouter';

const TEXTAREA =
  'w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30';

/** The assistant's part of a trace's panel: ask it, see what is sent, read its answers. Shown
 * only once the user chose an assistant. */
export function TraceAssistant({ entity }: { entity: Entity }) {
  const status = useAssistant();
  const on = status.data !== undefined && status.data.provider !== 'none';
  const annotations = useAnnotations(entity.id, on);
  const titleId = useId();
  if (!status.data || !on) return null;
  const list = annotations.data ?? [];
  const blocked = status.data.remote && !status.data.remote_ok;
  return (
    <section aria-labelledby={titleId} className="grid gap-2" data-testid="trace-assistant">
      <h3 id={titleId} className="flex items-center gap-1.5 text-sm font-semibold">
        <SparklesIcon aria-hidden className="size-4" />
        Assistant IA
      </h3>
      {blocked ? (
        <p className="text-sm text-muted-foreground">
          {PROVIDER_LABELS[status.data.provider]} envoie la trace hors de ta machine : autorise-le
          d’abord dans les{' '}
          <Link href="/reglages" className="underline underline-offset-2">
            Réglages
          </Link>
          .
        </p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {(['triage', 'explain'] as const).map((task) => (
              <AskButton key={task} entity={entity} task={task} busy={isBusy(latest(list, task))} />
            ))}
          </div>
          <SentText entityId={entity.id} status={status.data} />
        </>
      )}
      {annotations.isPending && <Pending label="Chargement des avis de l’IA…" />}
      {(['triage', 'explain'] as const).map((task) => {
        const annotation = latest(list, task);
        if (!annotation || annotation.decision === 'dismissed') return null;
        return <Answer key={task} entity={entity} annotation={annotation} />;
      })}
    </section>
  );
}

function AskButton({
  entity,
  task,
  busy,
}: {
  entity: Entity;
  task: AnnotationTask;
  busy: boolean;
}) {
  const ask = useAsk();
  return (
    <Button
      size="sm"
      variant="outline"
      disabled={busy || ask.isPending}
      onClick={() => ask.mutate({ entityId: entity.id, task })}
    >
      {TASK_LABELS[task]}
    </Button>
  );
}

/** The exact text a question sends, read before sending it. */
function SentText({ entityId, status }: { entityId: number; status: AssistantStatus }) {
  const [open, setOpen] = useState(false);
  const prompt = usePrompt(entityId, 'explain', open);
  const where = status.remote ? 'part chez Anthropic' : 'reste sur ta machine';
  return (
    <details className="text-sm" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="w-fit cursor-pointer text-muted-foreground underline-offset-2 hover:underline">
        Voir ce qui {where}
      </summary>
      <div className="mt-2 grid gap-1">
        {prompt.isPending && open && <Pending label="Préparation du texte…" />}
        {prompt.data && (
          <>
            <pre
              tabIndex={0}
              aria-label="Texte envoyé à l’assistant"
              className="max-h-64 overflow-auto rounded-md border bg-muted/40 p-2 text-xs whitespace-pre-wrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              data-testid="assistant-prompt"
            >
              {prompt.data.text}
            </pre>
            <p className="text-xs text-muted-foreground">
              « Est-ce bien moi ? » envoie le même texte, sans la ligne du score. Rien d’autre de
              ton profil ne part.
            </p>
          </>
        )}
      </div>
    </details>
  );
}

function Answer({ entity, annotation }: { entity: Entity; annotation: Annotation }) {
  const remove = useDeleteAnnotation();
  const ask = useAsk();
  let body: ReactNode;
  if (annotation.state === 'queued' || annotation.state === 'running') {
    body = (
      <p role="status" className="text-muted-foreground">
        {stateText(annotation, PROVIDER_LABELS[annotation.provider])}
      </p>
    );
  } else if (annotation.state === 'failed') {
    body = (
      <>
        <p role="alert">
          {messageFor(annotation.error_code ?? 'llm_failed', annotation.error_params ?? {})}
        </p>
        <div>
          <Button
            size="sm"
            variant="outline"
            disabled={ask.isPending}
            onClick={() => ask.mutate({ entityId: entity.id, task: annotation.task })}
          >
            Réessayer
          </Button>
        </div>
      </>
    );
  } else if (annotation.task === 'triage') {
    body = <TriageBody annotation={annotation} />;
  } else {
    body = <ExplainBody annotation={annotation} />;
  }
  return (
    <div
      className="grid gap-1.5 rounded-md border border-dashed p-2 text-sm"
      data-testid={`annotation-${annotation.task}`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Badge variant="secondary">Avis de l’IA</Badge>
          {TASK_LABELS[annotation.task]} · {answeredBy(annotation)} ·{' '}
          {formatDate(annotation.created_at)}
        </p>
        {annotation.state !== 'queued' && annotation.state !== 'running' && (
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Supprimer cet avis"
            disabled={remove.isPending}
            onClick={() => remove.mutate(annotation)}
          >
            <Trash2Icon aria-hidden />
          </Button>
        )}
      </div>
      {body}
    </div>
  );
}

function TriageBody({ annotation }: { annotation: Annotation }) {
  const update = useUpdateAnnotation();
  const verdict = verdictOf(annotation);
  const decide = (decision: 'accepted' | 'dismissed') =>
    update.mutate({ id: annotation.id, decision });
  return (
    <>
      {verdict && (
        <p className="font-medium" data-testid="annotation-verdict">
          {VERDICT_LABELS[verdict]}
        </p>
      )}
      <p>{textOf(annotation, 'reason')}</p>
      {annotation.decision === 'accepted' ? (
        <p className="text-xs text-muted-foreground">Appliqué au statut de la trace.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {verdict !== 'unsure' && verdict !== null && (
            <Button size="sm" disabled={update.isPending} onClick={() => decide('accepted')}>
              {verdict === 'me' ? 'Appliquer : c’est moi' : 'Appliquer : pas moi'}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            disabled={update.isPending}
            onClick={() => decide('dismissed')}
          >
            Ignorer
          </Button>
        </div>
      )}
    </>
  );
}

function ExplainBody({ annotation }: { annotation: Annotation }) {
  const update = useUpdateAnnotation();
  const [editing, setEditing] = useState(false);
  const [summary, setSummary] = useState('');
  const [risk, setRisk] = useState('');
  const id = useId();
  if (editing) {
    return (
      <form
        className="grid gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate(
            { id: annotation.id, output: { summary, risk } },
            { onSuccess: () => setEditing(false) },
          );
        }}
      >
        <div className="grid gap-1">
          <Label htmlFor={`${id}-summary`}>Ce que c’est</Label>
          <textarea
            id={`${id}-summary`}
            rows={3}
            maxLength={1000}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className={TEXTAREA}
          />
        </div>
        <div className="grid gap-1">
          <Label htmlFor={`${id}-risk`}>Ce que ça expose</Label>
          <textarea
            id={`${id}-risk`}
            rows={3}
            maxLength={1000}
            value={risk}
            onChange={(e) => setRisk(e.target.value)}
            className={TEXTAREA}
          />
        </div>
        <div className="flex gap-2">
          <Button size="sm" type="submit" disabled={update.isPending || !summary.trim()}>
            Enregistrer
          </Button>
          <Button size="sm" type="button" variant="ghost" onClick={() => setEditing(false)}>
            Annuler
          </Button>
        </div>
      </form>
    );
  }
  return (
    <>
      <p>{textOf(annotation, 'summary')}</p>
      <p>{textOf(annotation, 'risk')}</p>
      {annotation.edited && <p className="text-xs text-muted-foreground">Modifié par toi.</p>}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setSummary(textOf(annotation, 'summary'));
            setRisk(textOf(annotation, 'risk'));
            setEditing(true);
          }}
        >
          Modifier
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={update.isPending}
          onClick={() => update.mutate({ id: annotation.id, decision: 'dismissed' })}
        >
          Masquer
        </Button>
      </div>
    </>
  );
}
