import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useSourceTitle } from '@/features/graph/useTraceView';
import { get } from '@/lib/api';
import { saveFile } from '@/lib/download';
import { errorMessage } from '@/lib/errors';
import { exportName, toCsv, toReport, type ProfileExport } from '@/lib/report';
import { DownloadIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

type Format = 'html' | 'csv' | 'json';

/** The profile's exports: a report to read or print, its traces for a spreadsheet, or all of
 * it. Made on the user's click, saved where their browser saves downloads. */
export function ExportMenu({ profileId }: { profileId: number }) {
  const sourceTitle = useSourceTitle();
  const [busy, setBusy] = useState(false);

  const save = async (format: Format) => {
    setBusy(true);
    try {
      const data = await get<ProfileExport>(`/profiles/${profileId}/export`);
      if (format === 'html') {
        saveFile(exportName(data, 'html'), toReport(data, sourceTitle), 'text/html;charset=utf-8');
      } else if (format === 'csv') {
        saveFile(exportName(data, 'csv'), toCsv(data, sourceTitle), 'text/csv;charset=utf-8');
      } else {
        saveFile(
          exportName(data, 'json'),
          JSON.stringify(data, null, 2),
          'application/json;charset=utf-8',
        );
      }
      toast.success('Export enregistré dans tes téléchargements. Il contient tes données.');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={busy}>
          <DownloadIcon aria-hidden />
          Exporter
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Le fichier contiendra tes données</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void save('html')}>
          Rapport à lire ou imprimer (HTML)
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void save('csv')}>
          Les traces, pour un tableur (CSV)
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void save('json')}>Tout, en JSON</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
