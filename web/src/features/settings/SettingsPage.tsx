import { Pending } from '@/components/Pending';
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
import { useState, type FormEvent, type ReactNode } from 'react';
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
          <Token
            service="github"
            title="Token GitHub (facultatif)"
            saved={preferences.data.github_token_set}
            placeholder="github_pat_…"
          >
            Sans token, GitHub répond à 60 requêtes par heure, ce qui suffit pour un ou deux
            éléments. Un token personnel gratuit, sans aucune permission cochée, relève la limite à
            5 000. Il se crée dans GitHub : Settings → Developer settings → Personal access tokens.
          </Token>
          <Token
            service="gitlab"
            title="Token GitLab (facultatif)"
            saved={preferences.data.gitlab_token_set}
            placeholder="glpat-…"
          >
            Sans token, gitlab.com ne montre d’un profil que le nom et l’email public. Un token
            personnel gratuit, avec la seule permission « read_user », ajoute la bio, le lieu et le
            site. Il se crée dans GitLab : Preferences → Access tokens.
          </Token>
          <FediverseInstances instances={preferences.data.fediverse_instances} />
          <SearxngInstance
            address={preferences.data.searxng_url}
            autostart={preferences.data.searxng_autostart}
          />
          <AdultSites excluded={preferences.data.exclude_adult} />
          <Backups />
        </>
      )}
    </div>
  );
}

const SERVICE_NAMES = { github: 'GitHub', gitlab: 'GitLab' } as const;

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
          toast.success(`Token ${name} enregistré.`);
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
        {saved ? 'Un token est enregistré.' : 'Aucun token enregistré.'}
      </p>
      <form onSubmit={save} className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor={`${service}-token`}>{saved ? 'Remplacer le token' : 'Token'}</Label>
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
          Enregistrer
        </Button>
        {saved && (
          <Button
            type="button"
            variant="ghost"
            onClick={() =>
              update.mutate(
                { [key]: null },
                { onSuccess: () => toast.success(`Token ${name} retiré.`) },
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
          Instances Mastodon et Fediverse
        </h2>
        <p className="text-sm text-muted-foreground">
          Un pseudo est cherché sur une quinzaine de grandes instances (la liste est sur la page
          Sources). Ajoute ici celles où tu as, ou as eu, un compte : seules les instances de la
          liste sont contactées, et un pseudo@instance donné comme élément l’est sur la sienne.
        </p>
      </div>
      {instances.length > 0 ? (
        <ul className="flex flex-wrap gap-2" aria-label="Instances ajoutées">
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
                aria-label={`Retirer ${host}`}
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
        <p className="text-sm">Aucune instance ajoutée.</p>
      )}
      <form onSubmit={add} className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor="fediverse-instance">Instance</Label>
          <Input
            id="fediverse-instance"
            spellCheck={false}
            value={instance}
            onChange={(e) => setInstance(e.target.value)}
            placeholder="instance.example"
          />
        </div>
        <Button type="submit" disabled={!instance.trim() || update.isPending}>
          Ajouter
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
          Recherche web : ton instance SearXNG (facultatif)
        </h2>
        <p className="text-sm text-muted-foreground">
          Narcisse n’interroge jamais un moteur de recherche lui-même. SearXNG, un métamoteur qui
          tourne chez toi, peut le faire pendant les scans. Le bouton ci-dessous l’installe et la
          lance avec Docker, puis règle son adresse pour toi (il ouvre Docker Desktop s’il n’est pas
          déjà démarré). Sans elle, l’onglet « Recherche » d’un profil te prépare les recherches à
          faire toi-même.
        </p>
      </div>
      {status.data?.running && status.data.address && (
        <p className="text-sm" data-testid="searxng-state">
          SearXNG tourne sur <code className="text-foreground">{status.data.address}</code>, et
          Narcisse s’en sert pour la recherche web.
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
          {address ? 'Relancer SearXNG' : 'Installer et lancer avec Docker'}
        </Button>
        <p id="searxng-launch-state" className="text-sm text-muted-foreground" role="status">
          {launchState(status.data) ||
            (status.data && address && !status.data.running
              ? `SearXNG ne répond pas sur ${address} : il s’est sans doute arrêté avec l’ordinateur.`
              : '')}
        </p>
      </div>
      {address && (
        <Label className="flex items-start gap-2 font-normal">
          <Checkbox
            checked={autostart}
            onCheckedChange={(checked) => update.mutate({ searxng_autostart: checked === true })}
          />
          <span>
            Relancer SearXNG quand Narcisse démarre, s’il ne répond pas (après un redémarrage de
            l’ordinateur, par exemple). Docker Desktop s’ouvre si besoin.
          </span>
        </Label>
      )}
      <details className="text-sm">
        <summary className="w-fit cursor-pointer text-muted-foreground underline-offset-2 hover:underline">
          Régler l’adresse à la main
        </summary>
        <form onSubmit={save} className="mt-2 flex flex-wrap items-end gap-2">
          <div className="grid min-w-64 flex-1 gap-1.5">
            <Label htmlFor="searxng-url">Adresse de l’instance</Label>
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
            {value.trim() || !address ? 'Enregistrer' : 'Retirer'}
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
