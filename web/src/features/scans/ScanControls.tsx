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
import { useCancelScan, usePauseScan, useResumeScan } from '@/lib/queries';
import type { Scan } from '@/lib/types';
import { PauseIcon, PlayIcon, SquareIcon } from 'lucide-react';

/** Pause, resume, cancel. Each shows its effect at once; the server confirms within moments. */
export function ScanControls({ scan, size = 'sm' }: { scan: Scan; size?: 'sm' | 'default' }) {
  const pause = usePauseScan();
  const resume = useResumeScan();
  const cancel = useCancelScan();
  if (scan.status !== 'running' && scan.status !== 'paused') return null;

  return (
    <div className="flex flex-wrap gap-2">
      {scan.status === 'running' ? (
        <Button size={size} variant="outline" onClick={() => pause.mutate(scan.id)}>
          <PauseIcon aria-hidden />
          Pause
        </Button>
      ) : (
        <Button size={size} variant="outline" onClick={() => resume.mutate(scan.id)}>
          <PlayIcon aria-hidden />
          Reprendre
        </Button>
      )}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button size={size} variant="ghost">
            <SquareIcon aria-hidden />
            Annuler
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Annuler ce scan ?</AlertDialogTitle>
            <AlertDialogDescription>
              Les recherches en cours s’arrêtent. Les résultats déjà trouvés restent.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Continuer le scan</AlertDialogCancel>
            <AlertDialogAction onClick={() => cancel.mutate(scan.id)}>
              Annuler le scan
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
