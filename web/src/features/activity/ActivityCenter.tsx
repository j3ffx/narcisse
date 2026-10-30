import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { pullProgress } from '@/lib/assistant';
import { messageFor } from '@/lib/errors';
import { ACTIVE_SCAN } from '@/lib/labels';
import { useActivity, useCancelPull, useModelPull } from '@/lib/queries';
import { formatDate, useNow } from '@/lib/time';
import type { ScanDetail } from '@/lib/types';
import { ActivityIcon, DownloadIcon } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'wouter';
import { RunRow } from '../scans/RunRow';
import { ScanControls } from '../scans/ScanControls';
import { ScanStatusBadge } from '../scans/status';

/** Reachable from every screen: what runs, what waits, what failed, what just finished. */
export function ActivityCenter() {
  const [open, setOpen] = useState(false);
  const activity = useActivity();
  const pull = useModelPull();
  const scans = activity.data?.scans ?? [];
  const pulling = pull.data?.status === 'pulling';
  const active = scans.filter((s) => ACTIVE_SCAN.has(s.status)).length + (pulling ? 1 : 0);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="relative">
          <ActivityIcon aria-hidden />
          Activité
          {active > 0 && (
            <span
              className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-xs tabular-nums text-primary-foreground"
              aria-label={`${active} tâche${active > 1 ? 's' : ''} en cours`}
            >
              {active}
            </span>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Activité</SheetTitle>
          <SheetDescription>Les scans en cours et ceux des dernières 24 heures.</SheetDescription>
        </SheetHeader>
        <div className="grid gap-4 px-4 pb-6">
          {activity.data === undefined && (
            <p className="text-sm text-muted-foreground">Connexion à Narcisse…</p>
          )}
          {pull.data && pull.data.status !== 'idle' && <ModelDownload />}
          {activity.data !== undefined && scans.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Aucun scan en cours. Lance-en un depuis un profil.
            </p>
          )}
          {scans.map((scan) => (
            <ScanCard key={scan.id} scan={scan} onNavigate={() => setOpen(false)} />
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** A model Ollama downloads for the assistant: its progress, and a way to stop it. */
function ModelDownload() {
  const pull = useModelPull();
  const cancel = useCancelPull();
  const data = pull.data;
  if (!data) return null;
  const text = {
    idle: '',
    pulling: pullProgress(data.completed, data.total),
    done: 'Téléchargé : c’est le modèle de ton assistant.',
    failed: messageFor(data.error_code ?? 'pull_failed'),
    cancelled: 'Annulé.',
  }[data.status];
  return (
    <section
      className="grid gap-2 rounded-lg border p-3"
      aria-label={`Téléchargement de ${data.model ?? 'un modèle'}`}
      data-testid="activity-pull"
    >
      <p className="flex items-center gap-2 font-medium">
        <DownloadIcon aria-hidden className="size-4" />
        Modèle {data.model} pour l’assistant
      </p>
      {data.status === 'pulling' && data.total > 0 && (
        <progress
          className="h-2 w-full accent-primary"
          max={data.total}
          value={data.completed}
          aria-label="Progression du téléchargement"
        />
      )}
      <p className="text-sm" role={data.status === 'failed' ? 'alert' : 'status'}>
        {text}
      </p>
      {data.status === 'pulling' && (
        <div>
          <Button
            size="sm"
            variant="outline"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate()}
          >
            Annuler le téléchargement
          </Button>
        </div>
      )}
    </section>
  );
}

function ScanCard({ scan, onNavigate }: { scan: ScanDetail; onNavigate: () => void }) {
  const now = useNow();
  return (
    <section
      className="rounded-lg border p-3"
      aria-label={`Scan de ${scan.profile_name}`}
      data-testid="activity-scan"
      data-status={scan.status}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <Link
            href={`/scans/${scan.id}`}
            onClick={onNavigate}
            className="font-medium underline-offset-4 hover:underline"
          >
            {scan.profile_name}
          </Link>
          <p className="text-xs text-muted-foreground">
            {formatDate(scan.created_at)} · {scan.results_count} résultat
            {scan.results_count > 1 ? 's' : ''}
          </p>
        </div>
        <ScanStatusBadge status={scan.status} />
      </div>
      <ScanControls scan={scan} />
      <ul className="mt-1 divide-y">
        {scan.runs.map((run) => (
          <RunRow key={run.id} run={run} now={now} />
        ))}
      </ul>
    </section>
  );
}
