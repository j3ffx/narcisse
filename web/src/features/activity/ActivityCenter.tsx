import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { ACTIVE_SCAN } from '@/lib/labels';
import { useActivity } from '@/lib/queries';
import { formatDate, useNow } from '@/lib/time';
import type { ScanDetail } from '@/lib/types';
import { ActivityIcon } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'wouter';
import { RunRow } from '../scans/RunRow';
import { ScanControls } from '../scans/ScanControls';
import { ScanStatusBadge } from '../scans/status';

/** Reachable from every screen: what runs, what waits, what failed, what just finished. */
export function ActivityCenter() {
  const [open, setOpen] = useState(false);
  const activity = useActivity();
  const scans = activity.data?.scans ?? [];
  const active = scans.filter((s) => ACTIVE_SCAN.has(s.status)).length;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="relative">
          <ActivityIcon aria-hidden />
          Activité
          {active > 0 && (
            <span
              className="ml-1 rounded-full bg-primary px-1.5 text-xs leading-5 text-primary-foreground"
              aria-label={`${active} scan${active > 1 ? 's' : ''} en cours`}
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
          {activity.data !== undefined && scans.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Rien en cours. Lance un scan depuis un profil.
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
