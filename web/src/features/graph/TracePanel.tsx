import { AddAsSeed } from '@/components/AddAsSeed';
import { Pending } from '@/components/Pending';
import { ReviewButtons } from '@/components/ReviewButtons';
import { Button } from '@/components/ui/button';
import { errorMessage } from '@/lib/errors';
import { ENTITY_STATUS_LABELS, KIND_LABELS, RELATION_LABELS } from '@/lib/labels';
import { useEntityDetail } from '@/lib/queries';
import { points } from '@/lib/scores';
import { formatDate } from '@/lib/time';
import type { Edge, Entity, EntityDetail } from '@/lib/types';
import { ArrowLeftIcon, ArrowRightIcon, ExternalLinkIcon, XIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { KIND_ICONS } from './kinds';
import { Remediation } from './Remediation';
import { RiskValue, ScoreReasonsDetails } from './Scores';

const isLink = (text: string) => /^https?:\/\//.test(text);

/** Everything about one trace: what it is, how sure, where it was seen, what it relates to. */
export function TracePanel({
  profileId,
  id,
  onSelect,
  onClose,
  sourceTitle,
  actions,
  extra,
}: {
  profileId: number;
  id: number;
  onSelect: (id: number) => void;
  onClose: () => void;
  sourceTitle: (name: string) => string;
  actions?: ReactNode;
  /** A section shown after the trace's facts (e.g. the path finder). */
  extra?: ReactNode;
}) {
  const detail = useEntityDetail(id);
  return (
    <aside
      aria-label="Détail de la trace"
      className="flex max-h-full flex-col gap-4 overflow-y-auto rounded-lg border bg-card p-4"
      data-testid="trace-panel"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-heading text-lg font-semibold">Trace</h2>
        <Button variant="ghost" size="icon-sm" aria-label="Fermer le détail" onClick={onClose}>
          <XIcon aria-hidden />
        </Button>
      </div>
      {detail.isPending && <Pending label="Chargement de la trace…" />}
      {detail.isError && <p role="alert">{errorMessage(detail.error)}</p>}
      {detail.data && (
        <Detail
          profileId={profileId}
          data={detail.data}
          onSelect={onSelect}
          sourceTitle={sourceTitle}
          actions={actions}
          extra={extra}
        />
      )}
    </aside>
  );
}

function Detail({
  profileId,
  data,
  onSelect,
  sourceTitle,
  actions,
  extra,
}: {
  profileId: number;
  data: EntityDetail;
  onSelect: (id: number) => void;
  sourceTitle: (name: string) => string;
  actions?: ReactNode;
  extra?: ReactNode;
}) {
  const { entity } = data;
  const Icon = KIND_ICONS[entity.kind];
  const neighbours = new Map(data.neighbours.map((n) => [n.id, n]));
  return (
    <>
      <div className="grid gap-2">
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Icon aria-hidden className="size-4" />
          {KIND_LABELS[entity.kind]}
        </p>
        <p className="font-medium break-all" data-testid="trace-value">
          {isLink(entity.display) ? (
            <a
              href={entity.display}
              target="_blank"
              rel="noreferrer noopener"
              className="underline-offset-2 hover:underline"
            >
              {entity.display}
              <ExternalLinkIcon aria-hidden className="ml-1 inline size-3.5" />
            </a>
          ) : (
            entity.display
          )}
        </p>
        {entity.kind !== 'identity' && <ReviewButtons entity={entity} />}
        <AddAsSeed profileId={profileId} entity={entity} />
        {actions}
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Statut</dt>
        <dd>{ENTITY_STATUS_LABELS[entity.status]}</dd>
        {entity.confidence !== null && entity.kind !== 'identity' && (
          <>
            <dt className="text-muted-foreground">Confiance</dt>
            <dd data-testid="trace-confidence">{points(entity.confidence)} / 100</dd>
          </>
        )}
        {entity.risk !== null && entity.kind !== 'identity' && (
          <>
            <dt className="text-muted-foreground">Risque</dt>
            <dd data-testid="trace-risk">
              <RiskValue risk={entity.risk} />
            </dd>
          </>
        )}
        <dt className="text-muted-foreground">Sources</dt>
        <dd>
          {entity.modules
            .map((m) => (m === 'seed' ? 'déclaré par toi' : sourceTitle(m)))
            .join(', ') || '—'}
        </dd>
        <dt className="text-muted-foreground">Vue d’abord</dt>
        <dd>{formatDate(entity.first_seen)}</dd>
        <dt className="text-muted-foreground">Vue en dernier</dt>
        <dd>{formatDate(entity.last_seen)}</dd>
      </dl>
      <ScoreReasonsDetails reasons={data.reasons} />
      {entity.kind !== 'identity' && <Remediation entityId={entity.id} />}
      {extra}
      <Section title={`Relations (${data.edges.length})`}>
        <ul className="grid gap-1 text-sm">
          {data.edges.map((edge) => (
            <Relation
              key={edge.id}
              edge={edge}
              self={entity.id}
              other={neighbours.get(edge.source_id === entity.id ? edge.target_id : edge.source_id)}
              onSelect={onSelect}
            />
          ))}
        </ul>
      </Section>
      <Section title={`Preuves (${data.evidence.length})`}>
        {data.evidence.length === 0 && (
          <p className="text-sm text-muted-foreground">Déclaré par toi : rien à prouver.</p>
        )}
        <ul className="grid gap-3 text-sm">
          {data.evidence.map((proof) => (
            <li key={proof.id} className="grid gap-0.5 border-l-2 pl-2">
              <p className="text-xs text-muted-foreground">
                {sourceTitle(proof.module)} · {formatDate(proof.captured_at)}
                {proof.relation ? ` · ${RELATION_LABELS[proof.relation] ?? proof.relation}` : ''}
              </p>
              {proof.url && (
                <a
                  href={proof.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="break-all underline-offset-2 hover:underline"
                >
                  {proof.url}
                </a>
              )}
              {proof.excerpt && <p>{proof.excerpt}</p>}
              {proof.content_hash && (
                <p className="font-mono text-xs text-muted-foreground" title={proof.content_hash}>
                  empreinte {proof.content_hash.slice(0, 12)}…
                </p>
              )}
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

function Relation({
  edge,
  self,
  other,
  onSelect,
}: {
  edge: Edge;
  self: number;
  other: Entity | undefined;
  onSelect: (id: number) => void;
}) {
  const outgoing = edge.source_id === self;
  const Arrow = outgoing ? ArrowRightIcon : ArrowLeftIcon;
  const relation = RELATION_LABELS[edge.relation] ?? edge.relation;
  if (!other) return null;
  return (
    <li className="flex items-center gap-1.5">
      <Arrow aria-label={outgoing ? 'vers' : 'depuis'} className="size-3.5 shrink-0" />
      <span className="shrink-0 text-muted-foreground">{relation}</span>
      <button
        type="button"
        className="truncate text-left underline-offset-2 hover:underline focus-visible:underline"
        onClick={() => onSelect(other.id)}
        title={other.display}
      >
        {other.display}
      </button>
    </li>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}
