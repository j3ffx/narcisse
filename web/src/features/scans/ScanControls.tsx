import { t } from '@/i18n';
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
          {t().scanPage.pause}
        </Button>
      ) : (
        <Button size={size} variant="outline" onClick={() => resume.mutate(scan.id)}>
          <PlayIcon aria-hidden />
          {t().scanPage.resume}
        </Button>
      )}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button size={size} variant="ghost">
            <SquareIcon aria-hidden />
            {t().common.cancel}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t().scanPage.cancelTitle}</AlertDialogTitle>
            <AlertDialogDescription>{t().scanPage.cancelText}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t().scanPage.goOn}</AlertDialogCancel>
            <AlertDialogAction onClick={() => cancel.mutate(scan.id)}>
              {t().scanPage.cancelScan}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
