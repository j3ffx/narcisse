import { num, t } from '@/i18n';
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
import { useCreateProfile, useInfo, useMakeDemoGraph, useProfiles } from '@/lib/queries';
import type { ProfileKind } from '@/lib/types';
import { PlusIcon, WaypointsIcon } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useState, type FormEvent } from 'react';
import { Link, useLocation } from 'wouter';

export function ProfilesPage() {
  const profiles = useProfiles();
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold">{t().shell.profiles}</h1>
          <p className="text-sm text-muted-foreground">{t().profiles.intro}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <DemoGraphMenu />
          <NewProfileDialog />
        </div>
      </div>
      {profiles.isPending && <Pending label={t().profiles.loading} />}
      {profiles.isError && <p role="alert">{errorMessage(profiles.error)}</p>}
      {profiles.data?.length === 0 && (
        <p className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
          {t().profiles.none}
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
          navigate(`/profils/${profile.id}/elements`);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon aria-hidden />
          {t().profiles.new}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t().profiles.new}</DialogTitle>
            <DialogDescription>{t().profiles.newHint}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="profile-name">{t().profiles.name}</Label>
            <Input
              id="profile-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t().profiles.namePlaceholder}
              required
              maxLength={200}
              autoFocus
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="profile-kind">{t().profiles.kind}</Label>
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
              {create.isPending ? t().profiles.creating : t().profiles.create}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Demo mode: a fictitious profile with thousands of traces, to try the graph at scale. */
function DemoGraphMenu() {
  const info = useInfo();
  const make = useMakeDemoGraph();
  const [, navigate] = useLocation();
  if (!info.data?.demo) return null;
  const create = (nodes: number) =>
    make.mutate(nodes, { onSuccess: ({ profile_id }) => navigate(`/profils/${profile_id}`) });
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={make.isPending}>
          <WaypointsIcon aria-hidden />
          {make.isPending ? t().profiles.makingDemoGraph : t().profiles.demoGraph}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-auto">
        {[500, 5000, 20000].map((nodes) => (
          <DropdownMenuItem key={nodes} onSelect={() => create(nodes)}>
            {t().profiles.demoGraphOf(num(nodes))}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
