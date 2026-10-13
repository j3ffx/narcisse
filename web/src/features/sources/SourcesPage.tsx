import { Pending } from '@/components/Pending';
import { Badge } from '@/components/ui/badge';
import { errorMessage } from '@/lib/errors';
import { CATEGORY_LABELS, KIND_LABELS } from '@/lib/labels';
import { useInfo, useModules } from '@/lib/queries';
import type { Module } from '@/lib/types';

const SHOWN_HOSTS = 6;

/** What each source does and asks of whom, drawn from the modules' own descriptions. */
export function SourcesPage() {
  const modules = useModules();
  const info = useInfo();
  return (
    <div className="grid gap-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold">Sources</h1>
        <p className="text-sm text-muted-foreground">
          Ce que Narcisse interroge, à qui il le demande et à quel rythme. Toutes ces sources sont
          publiques et gratuites ; aucune ne se connecte à un compte.
          {info.data?.demo && ' En mode démo, seul le module de démonstration est proposé.'}
        </p>
      </div>
      {modules.isPending && <Pending label="Chargement des sources…" />}
      {modules.isError && <p role="alert">{errorMessage(modules.error)}</p>}
      <ul className="grid gap-4">
        {modules.data?.map((module) => (
          <SourceCard key={module.name} module={module} />
        ))}
      </ul>
    </div>
  );
}

function SourceCard({ module }: { module: Module }) {
  const rate = module.rate_limit;
  return (
    <li className="grid gap-2 rounded-lg border p-4" data-testid="source">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-heading text-lg font-semibold">{module.title}</h2>
        <Badge variant="secondary">{CATEGORY_LABELS[module.category] ?? module.category}</Badge>
        <Badge variant="outline">
          {module.intrusion === 'passive' ? 'Passif' : 'Actif léger (à activer)'}
        </Badge>
        {module.demo && <Badge variant="outline">fictif</Badge>}
      </div>
      <p className="text-sm">{module.description}</p>
      <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-muted-foreground">Part de</dt>
        <dd>{module.accepts.map((k) => KIND_LABELS[k]).join(', ')}</dd>
        <dt className="text-muted-foreground">Trouve</dt>
        <dd>{module.produces.map((k) => KIND_LABELS[k]).join(', ')}</dd>
        <dt className="text-muted-foreground">Contacte</dt>
        <dd>
          <Hosts hosts={module.hosts} other={module.other_hosts} />
        </dd>
        {rate && (
          <>
            <dt className="text-muted-foreground">Rythme</dt>
            <dd>
              au plus {rate.requests} requête{rate.requests > 1 ? 's' : ''} toutes les{' '}
              {rate.per_seconds} s par site
            </dd>
          </>
        )}
        {module.licence && (
          <>
            <dt className="text-muted-foreground">Licence</dt>
            <dd>{module.licence}</dd>
          </>
        )}
        {module.data_source && (
          <>
            <dt className="text-muted-foreground">Documentation</dt>
            <dd>
              <a
                href={module.data_source}
                target="_blank"
                rel="noreferrer noopener"
                className="break-all underline underline-offset-4"
              >
                {module.data_source}
              </a>
            </dd>
          </>
        )}
      </dl>
    </li>
  );
}

function Hosts({ hosts, other }: { hosts: string[]; other: string }) {
  if (hosts.length === 0) return <>{other || 'aucun site (rien ne sort de ta machine)'}</>;
  if (hosts.length <= SHOWN_HOSTS) return <>{[...hosts, ...(other ? [other] : [])].join(', ')}</>;
  return (
    <details>
      <summary className="cursor-pointer">{hosts.length} sites (voir la liste)</summary>
      <p className="mt-2 max-h-48 overflow-y-auto text-xs text-muted-foreground">
        {hosts.join(', ')}
      </p>
    </details>
  );
}
