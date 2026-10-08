import { Pending } from '@/components/Pending';
import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
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
import { PROFILE_KIND_LABELS } from '@/lib/labels';
import { useCreateProfile, useProfiles } from '@/lib/queries';
import type { ProfileKind } from '@/lib/types';
import { PlusIcon } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useLocation } from 'wouter';

export function ProfilesPage() {
  const profiles = useProfiles();
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold">Profils</h1>
          <p className="text-sm text-muted-foreground">
            Un profil rassemble ce qui t’identifie : noms, pseudos, emails… Narcisse part de là.
          </p>
        </div>
        <NewProfileDialog />
      </div>
      {profiles.isPending && <Pending label="Chargement des profils…" />}
      {profiles.isError && <p role="alert">{errorMessage(profiles.error)}</p>}
      {profiles.data?.length === 0 && (
        <p className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
          Aucun profil pour l’instant. Crée le premier, par exemple « Perso ».
        </p>
      )}
      <ul className="grid gap-3 sm:grid-cols-2">
        {profiles.data?.map((profile) => (
          <li key={profile.id}>
            <Link
              href={`/profils/${profile.id}`}
              className="block rounded-xl focus-visible:outline-2"
            >
              <Card className="transition-colors hover:bg-muted/50">
                <CardHeader>
                  <CardTitle>{profile.name}</CardTitle>
                  <CardDescription>{PROFILE_KIND_LABELS[profile.kind]}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function NewProfileDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [kind, setKind] = useState<ProfileKind>('personal');
  const create = useCreateProfile();
  const [, navigate] = useLocation();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { name, kind },
      {
        onSuccess: (profile) => {
          setOpen(false);
          setName('');
          navigate(`/profils/${profile.id}`);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon aria-hidden />
          Nouveau profil
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Nouveau profil</DialogTitle>
            <DialogDescription>
              Tu ajouteras ensuite ce qui t’identifie (noms, pseudos, emails…).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="profile-name">Nom du profil</Label>
            <Input
              id="profile-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jeanne Exemple (perso)"
              required
              maxLength={200}
              autoFocus
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="profile-kind">Type</Label>
            <Select value={kind} onValueChange={(v) => setKind(v as ProfileKind)}>
              <SelectTrigger id="profile-kind" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(PROFILE_KIND_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {create.isError && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-300">
              {errorMessage(create.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? 'Création…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
