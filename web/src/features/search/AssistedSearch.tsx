import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ENGINES, queriesFor } from '@/lib/dorks';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS } from '@/lib/labels';
import { useAddTrace } from '@/lib/queries';
import type { Seed } from '@/lib/types';
import { ExternalLinkIcon, PlusIcon } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { Link } from 'wouter';

/**
 * Searches to make by hand: Narcisse never asks a search engine, it prepares the queries and
 * opens them in the user's browser; the pages that are about them come back as traces.
 */
export function AssistedSearch({ profileId, seeds }: { profileId: number; seeds: Seed[] }) {
  const watched = seeds.filter((s) => s.status === 'watch');
  const groups = watched
    .map((seed) => ({ seed, queries: queriesFor(seed, watched) }))
    .filter((group) => group.queries.length > 0);
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
      <section className="grid gap-4" aria-labelledby="assisted-title">
        <div className="grid gap-1">
          <h2 id="assisted-title" className="font-heading text-lg font-semibold">
            Recherche assistée
          </h2>
          <p className="max-w-prose text-sm text-muted-foreground">
            Narcisse n’interroge pas les moteurs de recherche : il te prépare les recherches qui
            valent la peine, tu les ouvres dans ton navigateur. Quand une page parle de toi, colle
            son adresse dans le cadre « Ajouter une page » : elle rejoint tes traces.
          </p>
        </div>
        {groups.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Ajoute d’abord des éléments à surveiller (un nom, un pseudo, un email…).
          </p>
        )}
        {groups.map(({ seed, queries }) => (
          <section key={seed.id} className="grid gap-2" data-testid="assisted-seed">
            <h3 className="text-sm font-semibold">
              {KIND_LABELS[seed.kind]} : <span className="font-normal">{seed.value}</span>
            </h3>
            <ul className="grid gap-2">
              {queries.map(({ query, why }) => (
                <li key={query} className="grid gap-1 rounded-md border bg-card p-3">
                  <code className="text-sm break-all">{query}</code>
                  <p className="text-xs text-muted-foreground">{why}</p>
                  <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
                    {ENGINES.map((engine) => (
                      <a
                        key={engine.name}
                        href={engine.url(query)}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1 text-primary underline-offset-2 visited:text-muted-foreground hover:underline"
                        aria-label={`Chercher ${query} sur ${engine.name} (nouvel onglet)`}
                      >
                        {engine.name}
                        <ExternalLinkIcon aria-hidden className="size-3" />
                      </a>
                    ))}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </section>
      <AddTrace profileId={profileId} />
    </div>
  );
}

function AddTrace({ profileId }: { profileId: number }) {
  const add = useAddTrace(profileId);
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [added, setAdded] = useState<number | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate(
      { url: url.trim(), note: note.trim() },
      {
        onSuccess: (entity) => {
          setAdded(entity.id);
          setUrl('');
          setNote('');
          toast.success('Page ajoutée à tes traces.');
        },
      },
    );
  };
  return (
    <form
      onSubmit={submit}
      className="grid gap-3 rounded-lg border bg-card p-4 lg:sticky lg:top-4"
      aria-labelledby="add-trace-title"
    >
      <h2 id="add-trace-title" className="font-heading text-lg font-semibold">
        Ajouter une page
      </h2>
      <div className="grid gap-1.5">
        <Label htmlFor="trace-url">Adresse d’une page qui parle de toi</Label>
        <Input
          id="trace-url"
          type="url"
          required
          inputMode="url"
          placeholder="https://…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="trace-note">Ce qu’elle dit de toi (facultatif)</Label>
        <Input
          id="trace-note"
          maxLength={500}
          placeholder="Mon nom dans un compte rendu…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      {add.isError && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {errorMessage(add.error)}
        </p>
      )}
      <Button type="submit" className="w-fit" disabled={add.isPending || !url.trim()}>
        <PlusIcon aria-hidden />
        {add.isPending ? 'Ajout…' : 'Ajouter à mes traces'}
      </Button>
      {added !== null && (
        <p className="text-sm" role="status">
          Ajoutée :{' '}
          <Link
            href={`/profils/${profileId}?trace=${added}`}
            className="break-all underline underline-offset-2"
          >
            la voir dans le graphe
          </Link>
          .
        </p>
      )}
    </form>
  );
}
