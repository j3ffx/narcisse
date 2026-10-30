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
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError, post } from '@/lib/api';
import { saveFile } from '@/lib/download';
import { errorMessage } from '@/lib/errors';
import { formatDay } from '@/lib/remediation';
import type { Restored } from '@/lib/types';
import { ArchiveIcon, ArchiveRestoreIcon } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';
import { toast } from 'sonner';

/** Backing up all of Narcisse's data, and restoring a backup. */
export function Backups() {
  const id = useId();
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-4" data-testid="backups">
      <div>
        <h2 id={`${id}-title`} className="font-heading text-lg font-semibold">
          {t().backups.title}
        </h2>
        <p className="text-sm text-muted-foreground">{t().backups.intro}</p>
      </div>
      <MakeBackup />
      <RestoreBackup />
    </section>
  );
}

function fileName(response: Response): string {
  const match = /filename="([^"]+)"/.exec(response.headers.get('content-disposition') ?? '');
  return match?.[1] ?? 'narcisse.narcisse';
}

function MakeBackup() {
  const id = useId();
  const [passphrase, setPassphrase] = useState('');
  const [busy, setBusy] = useState(false);
  const make = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await fetch('/api/backup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passphrase: passphrase || null }),
      });
      if (!response.ok) throw new ApiError('internal_error', {}, response.status);
      saveFile(fileName(response), await response.blob(), 'application/octet-stream');
      setPassphrase('');
      toast.success(t().backups.saved);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={make} className="grid gap-2">
      <div className="grid max-w-md gap-1.5">
        <Label htmlFor={`${id}-passphrase`}>{t().backups.passphrase}</Label>
        <Input
          id={`${id}-passphrase`}
          type="password"
          autoComplete="new-password"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          aria-describedby={`${id}-help`}
        />
        <p id={`${id}-help`} className="text-xs text-muted-foreground">
          {t().backups.passphraseHelp}
        </p>
      </div>
      <Button type="submit" disabled={busy} className="w-fit">
        <ArchiveIcon aria-hidden />
        {busy ? t().backups.saving : t().backups.download}
      </Button>
    </form>
  );
}

function asBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '');
    reader.onerror = () => reject(new ApiError('backup_invalid'));
    reader.readAsDataURL(file);
  });
}

function RestoreBackup() {
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [passphrase, setPassphrase] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const restore = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const data = await asBase64(file);
      const restored = await post<Restored>('/restore', {
        data,
        passphrase: passphrase || null,
      });
      toast.success(
        t().backups.restored(restored.profiles, formatDay(restored.created_at), restored.safety),
        { duration: 15_000 },
      );
      // Everything shown came from the data just replaced: start afresh.
      setTimeout(() => window.location.assign('/'), 1500);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-2">
      <h3 className="text-sm font-semibold">{t().backups.restoreTitle}</h3>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-file`}>{t().backups.file}</Label>
          <Input
            id={`${id}-file`}
            type="file"
            accept=".narcisse"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setError(null);
            }}
            className="max-w-xs"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}-restore-passphrase`}>{t().backups.itsPassphrase}</Label>
          <Input
            id={`${id}-restore-passphrase`}
            type="password"
            autoComplete="off"
            value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)}
            className="max-w-xs"
          />
        </div>
        <Button variant="outline" disabled={!file || busy} onClick={() => setConfirming(true)}>
          <ArchiveRestoreIcon aria-hidden />
          {busy ? t().backups.restoring : t().backups.restore}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t().backups.confirmTitle}</AlertDialogTitle>
            <AlertDialogDescription>{t().backups.confirmText}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t().common.cancel}</AlertDialogCancel>
            <AlertDialogAction onClick={() => void restore()}>
              {t().backups.restore}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
