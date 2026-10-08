import { Pending } from '@/components/Pending';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { ScanStatusBadge } from '@/features/scans/status';
import { errorMessage } from '@/lib/errors';
import { KIND_LABELS, PROFILE_KIND_LABELS } from '@/lib/labels';
import { useDeleteProfile, useModules, useProfile, useScans, useStartScan } from '@/lib/queries';
import { formatDate } from '@/lib/time';
import type { ProfileDetail } from '@/lib/types';
import { RadarIcon, Trash2Icon } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation } from 'wouter';
import { SeedsEditor } from './SeedsEditor';

export function ProfilePage({ id }: { id: number }) {
  const profile = useProfile(id);
  if (profile.isPending) return <Pending label="Chargement du profil…" />;
  if (profile.isError) return <p role="alert">{errorMessage(profile.error)}</p>;
  const data = profile.data;

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            <Link href="/" className="hover:underline">
              Profils
            </Link>{' '}
            · {PROFILE_KIND_LABELS[data.kind]}
          </p>
          <h1 className="font-heading text-2xl font-semibold">{data.name}</h1>
        </div>
        <div className="flex gap-2">
          <StartScanDialog profile={data} />
          <DeleteProfile id={id} name={data.name} />
        </div>
      </div>
      <SeedsEditor profileId={id} seeds={data.seeds} />
      <ScanHistory profileId={id} />
    </div>
  );
}

function StartScanDialog({ profile }: { profile: ProfileDetail }) {
  const modules = useModules();
  const start = useStartScan(profile.id);
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<string[] | null>(null);
  const [, navigate] = useLocation();
  const watched = profile.seeds.filter((s) => s.status === 'watch');
  const kinds = new Set(watched.map((s) => s.kind));
  const usable = (modules.data ?? []).filter((m) => m.accepts.some((k) => kinds.has(k as never)));
  const selected = chosen ?? usable.map((m) => m.name);

  const launch = () =>
    start.mutate(selected, {
      onSuccess: (scan) => {
        setOpen(false);
        navigate(`/scans/${scan.id}`);
      },
    });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setChosen(null);
          start.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button disabled={watched.length === 0}>
          <RadarIcon aria-hidden />
          Lancer un scan
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Lancer un scan</DialogTitle>
          <DialogDescription>
            {watched.length} élément{watched.length > 1 ? 's' : ''} surveillé
            {watched.length > 1 ? 's' : ''}. Choisis les sources à interroger.
          </DialogDescription>
        </DialogHeader>
        {modules.isPending && <Pending label="Chargement des sources…" />}
        {modules.data && usable.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Aucune source disponible pour ces éléments pour l’instant.
          </p>
        )}
        <ul className="grid gap-3">
          {usable.map((module) => {
            const id = `module-${module.name}`;
            return (
              <li key={module.name} className="flex gap-3">
                <Checkbox
                  id={id}
                  checked={selected.includes(module.name)}
                  onCheckedChange={(checked) =>
                    setChosen(
                      checked
                        ? [...selected, module.name]
                        : selected.filter((n) => n !== module.name),
                    )
                  }
                />
                <div className="grid gap-0.5">
                  <Label htmlFor={id}>
                    {module.title}
                    {module.demo && (
                      <span className="rounded bg-amber-100 px-1.5 text-xs text-amber-950 dark:bg-amber-950 dark:text-amber-50">
                        fictif
                      </span>
                    )}
                  </Label>
                  <p className="text-sm text-muted-foreground">{module.description}</p>
                  <p className="text-xs text-muted-foreground">
                    Accepte :{' '}
                    {module.accepts
                      .filter((k) => kinds.has(k as never))
                      .map((k) => KIND_LABELS[k])
                      .join(', ')}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
        {start.isError && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-300">
            {errorMessage(start.error)}
          </p>
        )}
        <DialogFooter>
          <Button onClick={launch} disabled={start.isPending || selected.length === 0}>
            {start.isPending ? 'Lancement…' : 'Lancer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteProfile({ id, name }: { id: number; name: string }) {
  const remove = useDeleteProfile(id);
  const [, navigate] = useLocation();
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Supprimer le profil">
          <Trash2Icon aria-hidden />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Supprimer « {name} » ?</AlertDialogTitle>
          <AlertDialogDescription>
            Le profil, ses éléments, ses scans et tout ce qu’ils ont trouvé sont effacés de cet
            ordinateur.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Garder</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => remove.mutate(undefined, { onSuccess: () => navigate('/') })}
          >
            Supprimer
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ScanHistory({ profileId }: { profileId: number }) {
  const scans = useScans(profileId);
  return (
    <section aria-labelledby="scans-title" className="grid gap-3">
      <h2 id="scans-title" className="font-heading text-lg font-semibold">
        Scans
      </h2>
      {scans.isPending && <Pending label="Chargement des scans…" />}
      {scans.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun scan encore.</p>
      )}
      <ul className="divide-y rounded-lg border empty:hidden">
        {scans.data?.map((scan) => (
          <li key={scan.id}>
            <Link
              href={`/scans/${scan.id}`}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 hover:bg-muted/50"
            >
              <span>{formatDate(scan.created_at)}</span>
              <span className="flex items-center gap-3 text-sm text-muted-foreground">
                {scan.results_count} résultat{scan.results_count > 1 ? 's' : ''}
                <ScanStatusBadge status={scan.status} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
