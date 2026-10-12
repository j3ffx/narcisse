import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { useInfo, usePreferences, useUpdatePreferences } from '@/lib/queries';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

export function SettingsPage() {
  const preferences = usePreferences();
  const info = useInfo();
  return (
    <div className="grid max-w-2xl gap-8">
      <div>
        <h1 className="font-heading text-2xl font-semibold">Réglages</h1>
        <p className="text-sm text-muted-foreground">
          Rangés sur cette machine
          {info.data ? ` (${info.data.data_dir})` : ''}, jamais envoyés ailleurs.
        </p>
      </div>
      {preferences.isPending && <Pending label="Chargement des réglages…" />}
      {preferences.isError && <p role="alert">{errorMessage(preferences.error)}</p>}
      {preferences.data && (
        <>
          <GitHubToken saved={preferences.data.github_token_set} />
          <AdultSites excluded={preferences.data.exclude_adult} />
        </>
      )}
    </div>
  );
}

function GitHubToken({ saved }: { saved: boolean }) {
  const [token, setToken] = useState('');
  const update = useUpdatePreferences();
  const save = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      { github_token: token },
      {
        onSuccess: () => {
          setToken('');
          toast.success('Token GitHub enregistré.');
        },
      },
    );
  };
  return (
    <section aria-labelledby="github-title" className="grid gap-3">
      <div>
        <h2 id="github-title" className="font-heading text-lg font-semibold">
          Token GitHub (facultatif)
        </h2>
        <p className="text-sm text-muted-foreground">
          Sans token, GitHub répond à 60 requêtes par heure, ce qui suffit pour un ou deux éléments.
          Un token personnel gratuit, sans aucune permission cochée, relève la limite à 5 000. Il se
          crée dans GitHub : Settings → Developer settings → Personal access tokens.
        </p>
      </div>
      <p className="text-sm" data-testid="github-token-state">
        {saved ? 'Un token est enregistré.' : 'Aucun token enregistré.'}
      </p>
      <form onSubmit={save} className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor="github-token">{saved ? 'Remplacer le token' : 'Token'}</Label>
          <Input
            id="github-token"
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="github_pat_…"
          />
        </div>
        <Button type="submit" disabled={!token.trim() || update.isPending}>
          Enregistrer
        </Button>
        {saved && (
          <Button
            type="button"
            variant="ghost"
            onClick={() =>
              update.mutate(
                { github_token: null },
                { onSuccess: () => toast.success('Token GitHub retiré.') },
              )
            }
          >
            Retirer
          </Button>
        )}
      </form>
    </section>
  );
}

function AdultSites({ excluded }: { excluded: boolean }) {
  const update = useUpdatePreferences();
  return (
    <section aria-labelledby="adult-title" className="grid gap-3">
      <h2 id="adult-title" className="font-heading text-lg font-semibold">
        Sites adultes
      </h2>
      <p className="text-sm text-muted-foreground">
        La recherche de comptes par pseudo vérifie aussi une quarantaine de sites adultes : un
        compte oublié là-bas est souvent la trace la plus gênante. Les comptes trouvés portent
        l’étiquette « site adulte ».
      </p>
      <Label className="flex items-center gap-2 font-normal">
        <Checkbox
          checked={excluded}
          onCheckedChange={(checked) => update.mutate({ exclude_adult: checked === true })}
        />
        Ne pas vérifier les sites adultes
      </Label>
    </section>
  );
}
