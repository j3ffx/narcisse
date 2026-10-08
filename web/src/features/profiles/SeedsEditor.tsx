import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS, SEED_EXAMPLES, SEED_KINDS } from '@/lib/labels';
import { useAddSeed, useDeleteSeed, useUpdateSeed } from '@/lib/queries';
import type { Seed, SeedKind } from '@/lib/types';
import { EyeIcon, EyeOffIcon, PlusIcon, Trash2Icon } from 'lucide-react';
import { useState, type FormEvent } from 'react';

/** What identifies the person: the starting points of every scan. */
export function SeedsEditor({ profileId, seeds }: { profileId: number; seeds: Seed[] }) {
  const [kind, setKind] = useState<SeedKind>('name');
  const [value, setValue] = useState('');
  const add = useAddSeed(profileId);
  const update = useUpdateSeed(profileId);
  const remove = useDeleteSeed(profileId);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate({ kind, value }, { onSuccess: () => setValue('') });
  };

  return (
    <section aria-labelledby="seeds-title" className="grid gap-3">
      <div>
        <h2 id="seeds-title" className="font-heading text-lg font-semibold">
          Ce qui t’identifie
        </h2>
        <p className="text-sm text-muted-foreground">
          Les scans partent de ces éléments. Un élément ignoré reste noté mais n’est pas cherché.
        </p>
      </div>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="grid gap-1.5">
          <Label htmlFor="seed-kind">Type</Label>
          <Select value={kind} onValueChange={(v) => setKind(v as SeedKind)}>
            <SelectTrigger id="seed-kind" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SEED_KINDS.map((k) => (
                <SelectItem key={k} value={k}>
                  {KIND_LABELS[k]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid min-w-56 flex-1 gap-1.5">
          <Label htmlFor="seed-value">Valeur</Label>
          <Input
            id="seed-value"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              add.reset();
            }}
            placeholder={SEED_EXAMPLES[kind]}
            required
            maxLength={500}
            aria-invalid={add.isError}
            aria-describedby={add.isError ? 'seed-error' : undefined}
          />
        </div>
        <Button type="submit" disabled={add.isPending || !value.trim()}>
          <PlusIcon aria-hidden />
          Ajouter
        </Button>
      </form>
      {add.isError && (
        <p id="seed-error" role="alert" className="text-sm text-red-700 dark:text-red-300">
          {errorMessage(add.error)}
        </p>
      )}
      {seeds.length === 0 ? (
        <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Rien encore. Commence par ton nom, un pseudo ou un email.
        </p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {seeds.map((seed) => {
            const ignored = seed.status === 'ignore';
            return (
              <li key={seed.id} className="flex items-center gap-3 px-3 py-2" data-testid="seed">
                <span className="w-28 shrink-0 text-xs text-muted-foreground">
                  {KIND_LABELS[seed.kind]}
                </span>
                <span
                  className={
                    ignored
                      ? 'min-w-0 flex-1 truncate line-through opacity-60'
                      : 'min-w-0 flex-1 truncate'
                  }
                >
                  {seed.value}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-pressed={ignored}
                  onClick={() =>
                    update.mutate({ id: seed.id, status: ignored ? 'watch' : 'ignore' })
                  }
                >
                  {ignored ? <EyeOffIcon aria-hidden /> : <EyeIcon aria-hidden />}
                  {ignored ? 'Ignoré' : 'Surveillé'}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Retirer ${seed.value}`}
                  onClick={() => remove.mutate(seed.id)}
                >
                  <Trash2Icon aria-hidden />
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
