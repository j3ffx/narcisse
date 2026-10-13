import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { get } from '@/lib/api';
import { errorMessage } from '@/lib/errors';
import { sha1Hex } from '@/lib/sha1';
import { ShieldAlertIcon, ShieldCheckIcon } from 'lucide-react';
import { useState, type FormEvent } from 'react';

/** How many times a password appears in known breaches: 0 when it doesn't. */
async function timesLeaked(password: string): Promise<number> {
  const hash = await sha1Hex(password);
  const prefix = hash.slice(0, 5);
  const { suffixes } = await get<{ suffixes: [string, number][] }>(`/pwned-passwords/${prefix}`);
  return suffixes.find(([suffix]) => prefix + suffix === hash)?.[1] ?? 0;
}

/**
 * Has a password leaked? Pwned Passwords by k-anonymity: the password never leaves the page,
 * only the first five characters of its SHA-1 go out; nothing is kept.
 */
export function PasswordCheck() {
  const [password, setPassword] = useState('');
  // The answer only: the password itself is kept nowhere but in the field, cleared once checked.
  const [check, setCheck] = useState<
    | { state: 'idle' | 'pending' }
    | { state: 'done'; times: number }
    | { state: 'failed'; error: unknown }
  >({ state: 'idle' });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setCheck({ state: 'pending' });
    timesLeaked(password).then(
      (times) => setCheck({ state: 'done', times }),
      (error: unknown) => setCheck({ state: 'failed', error }),
    );
    setPassword('');
  };
  return (
    <div className="grid max-w-2xl gap-6">
      <div className="grid gap-2">
        <h1 className="font-heading text-2xl font-semibold">Un mot de passe a-t-il fuité ?</h1>
        <p className="text-muted-foreground">
          Narcisse cherche ton mot de passe parmi les centaines de millions qu’ont révélés des
          fuites de données, sans jamais le faire sortir de cette page : elle calcule son empreinte
          (SHA-1), n’en envoie que les 5 premiers caractères à Pwned Passwords, qui répond avec
          toutes les empreintes qui commencent pareil, et la comparaison se fait ici. Rien n’est
          gardé.
        </p>
      </div>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor="password">Mot de passe à vérifier</Label>
          <Input
            id="password"
            type="password"
            autoComplete="off"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setCheck({ state: 'idle' });
            }}
          />
        </div>
        <Button type="submit" disabled={!password || check.state === 'pending'}>
          {check.state === 'pending' ? 'Vérification…' : 'Vérifier'}
        </Button>
      </form>
      <div aria-live="polite">
        {check.state === 'failed' && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-300">
            {errorMessage(check.error)}
          </p>
        )}
        {check.state === 'done' &&
          (check.times > 0 ? (
            <p className="flex gap-2 rounded-lg border border-red-300 p-3 dark:border-red-800">
              <ShieldAlertIcon aria-hidden className="mt-0.5 size-5 shrink-0" />
              <span>
                Ce mot de passe apparaît <strong>{check.times.toLocaleString('fr-FR')} fois</strong>{' '}
                dans des fuites connues : ne l’utilise plus nulle part, et change-le là où tu t’en
                sers encore.
              </span>
            </p>
          ) : (
            <p className="flex gap-2 rounded-lg border p-3">
              <ShieldCheckIcon aria-hidden className="mt-0.5 size-5 shrink-0" />
              <span>
                Ce mot de passe n’apparaît dans aucune fuite connue. Ça ne veut pas dire qu’il est
                solide : long et unique pour chaque site reste la règle.
              </span>
            </p>
          ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Données : Pwned Passwords, de Have I Been Pwned (Troy Hunt), licence CC BY 4.0.
      </p>
    </div>
  );
}
