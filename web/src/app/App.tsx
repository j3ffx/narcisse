import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ProfilePage, type ProfileTab } from '@/features/profiles/ProfilePage';
import { ProfilesPage } from '@/features/profiles/ProfilesPage';
import { ScanPage } from '@/features/scans/ScanPage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { SourcesPage } from '@/features/sources/SourcesPage';
import { useLiveUpdates } from '@/hooks/useLiveUpdates';
import { Link, Route, Switch } from 'wouter';
import { AppShell } from './AppShell';

export function App() {
  const connection = useLiveUpdates();
  return (
    <TooltipProvider>
      <AppShell connection={connection}>
        <Switch>
          <Route path="/" component={ProfilesPage} />
          <Route path="/profils/:id/:tab?">
            {(p) =>
              p.tab === undefined || ['liste', 'elements', 'scans'].includes(p.tab) ? (
                <ProfilePage id={Number(p.id)} key={p.id} tab={(p.tab ?? 'graphe') as ProfileTab} />
              ) : (
                <NotFound />
              )
            }
          </Route>
          <Route path="/sources" component={SourcesPage} />
          <Route path="/reglages" component={SettingsPage} />
          <Route path="/scans/:id">{(p) => <ScanPage id={Number(p.id)} key={p.id} />}</Route>
          <Route>
            <NotFound />
          </Route>
        </Switch>
      </AppShell>
      <Toaster position="bottom-right" />
    </TooltipProvider>
  );
}

function NotFound() {
  return (
    <div className="grid gap-2">
      <h1 className="font-heading text-2xl font-semibold">Page introuvable</h1>
      <Link href="/" className="underline">
        Retour aux profils
      </Link>
    </div>
  );
}
