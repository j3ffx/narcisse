import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { useInfo, useModules, usePreferences, useUpdatePreferences } from '@/lib/queries';
import type { Module } from '@/lib/types';
import { XIcon } from 'lucide-react';
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
          <SearxngInstance address={preferences.data.searxng_url} />
          <LightActive enabled={preferences.data.enabled_light_active} />
          <AdultSites excluded={preferences.data.exclude_adult} />
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

function SearxngInstance({ address }: { address: string | null }) {
  const [value, setValue] = useState(address ?? '');
  const update = useUpdatePreferences();
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
          tourne chez toi, peut le faire pendant les scans. Pour en installer une avec Docker :{' '}
          <code className="text-foreground">uv run narcisse searxng</code>, qui la lance et règle
          son adresse ici. Sans elle, l’onglet « Recherche » d’un profil te prépare les recherches à
          faire toi-même.
        </p>
      </div>
      <form onSubmit={save} className="flex flex-wrap items-end gap-2">
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
        <Button type="submit" disabled={update.isPending || value.trim() === (address ?? '')}>
          {value.trim() || !address ? 'Enregistrer' : 'Retirer'}
        </Button>
      </form>
    </section>
  );
}

function LightActive({ enabled }: { enabled: string[] }) {
  const modules = useModules();
  const update = useUpdatePreferences();
  const lightActive = (modules.data ?? []).filter((m) => m.intrusion === 'light_active');
  if (lightActive.length === 0) return null;
  const toggle = (module: Module, on: boolean) => {
    const next = on
      ? [...enabled, module.name]
      : enabled.filter((name) => name !== module.name);
    update.mutate(
      { enabled_light_active: next },
      {
        onSuccess: () =>
          toast.success(on ? `${module.title} activé.` : `${module.title} désactivé.`),
      },
    );
  };
  return (
    <section aria-labelledby="light-active-title" className="grid gap-3">
      <div>
        <h2 id="light-active-title" className="font-heading text-lg font-semibold">
          Sources « actif léger »
        </h2>
        <p className="text-sm text-muted-foreground">
          Ces sources ne lisent pas une page publique : elles <strong>sollicitent un service</strong>{' '}
          pour savoir si une adresse email y est inscrite, via son formulaire de mot de passe oublié,
          sans jamais s’y connecter, créer de compte ni envoyer d’email au titulaire. Narcisse se
          limite aux services qui répondent discrètement. Chacune est <strong>désactivée</strong> tant
          que tu ne l’actives pas ici, et n’est alors utilisée que si tu la coches au moment du scan.
        </p>
      </div>
      <ul className="grid gap-3">
        {lightActive.map((module) => {
          const on = enabled.includes(module.name);
          return (
            <li key={module.name} className="rounded-md border p-3">
              <Label className="flex items-start gap-2 font-normal">
                <Checkbox
                  className="mt-0.5"
                  checked={on}
                  disabled={update.isPending}
                  onCheckedChange={(checked) => toggle(module, checked === true)}
                />
                <span className="grid gap-0.5">
                  <span className="font-medium text-foreground">{module.title}</span>
                  <span className="text-sm text-muted-foreground">{module.description}</span>
                </span>
              </Label>
            </li>
          );
        })}
      </ul>
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
