import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ProfilePage } from '@/features/profiles/ProfilePage';
import { isProfileTab, type ProfileTab } from '@/features/profiles/tabs';
import { ProfilesPage } from '@/features/profiles/ProfilesPage';
import { ScanPage } from '@/features/scans/ScanPage';
import { PasswordCheck } from '@/features/passwords/PasswordCheck';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { SourcesPage } from '@/features/sources/SourcesPage';
import { useLiveUpdates } from '@/hooks/useLiveUpdates';
import { resolveLang, setLang, t, useLang } from '@/i18n';
import { usePreferences } from '@/lib/queries';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Link, Route, Switch, useLocation } from 'wouter';
import { AppShell } from './AppShell';

export function App() {
  const connection = useLiveUpdates();
  // A crash stays on its page: going elsewhere starts afresh.
  const [location] = useLocation();
  const lang = useLang();
  useLanguage();
  // The whole app is drawn again in the new language (and the server's texts asked again).
  return (
    <TooltipProvider key={lang}>
      <AppShell connection={connection}>
        <ErrorBoundary key={location} label={t().shell.thisPage}>
          <Switch>
            <Route path="/" component={ProfilesPage} />
            <Route path="/profils/:id/:tab?">
              {(p) =>
                p.tab === undefined || isProfileTab(p.tab) ? (
                  <ProfilePage
                    id={Number(p.id)}
                    key={p.id}
                    tab={(p.tab ?? 'graphe') as ProfileTab}
                  />
                ) : (
                  <NotFound />
                )
              }
            </Route>
            <Route path="/sources" component={SourcesPage} />
            <Route path="/reglages" component={SettingsPage} />
            <Route path="/mot-de-passe" component={PasswordCheck} />
            <Route path="/scans/:id">{(p) => <ScanPage id={Number(p.id)} key={p.id} />}</Route>
            <Route>
              <NotFound />
            </Route>
          </Switch>
        </ErrorBoundary>
      </AppShell>
      <Toaster position="bottom-right" />
    </TooltipProvider>
  );
}

/** The language chosen in the settings (the browser's by default), and the server's texts
 * (proofs, sources) asked again when it changes. */
function useLanguage() {
  const preferences = usePreferences();
  const client = useQueryClient();
  const choice = preferences.data?.ui_lang;
  useEffect(() => {
    if (choice === undefined) return;
    const next = resolveLang(choice);
    if (next === document.documentElement.lang) return;
    setLang(next);
    void client.invalidateQueries({ predicate: (query) => query.queryKey[0] !== 'preferences' });
  }, [choice, client]);
}

function NotFound() {
  return (
    <div className="grid gap-2">
      <h1 className="font-heading text-2xl font-semibold">{t().shell.notFound}</h1>
      <Link href="/" className="underline">
        {t().shell.backToProfiles}
      </Link>
    </div>
  );
}
