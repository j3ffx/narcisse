import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ActivityCenter } from '@/features/activity/ActivityCenter';
import type { Connection } from '@/hooks/useLiveUpdates';
import { useInfo } from '@/lib/queries';
import { MonitorIcon, MoonIcon, SunIcon, WifiOffIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'wouter';
import { useTheme, type ThemeChoice } from './theme';

export function AppShell({
  connection,
  children,
}: {
  connection: Connection;
  children: ReactNode;
}) {
  const info = useInfo();
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-background focus:px-3 focus:py-2"
      >
        Aller au contenu
      </a>
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2.5">
          <Link href="/" className="flex items-center gap-2 font-heading text-lg font-semibold">
            <img src="/favicon.svg" alt="" className="size-6" />
            Narcisse
          </Link>
          <nav aria-label="Navigation" className="ml-2 text-sm">
            <Link href="/" className="text-muted-foreground hover:text-foreground">
              Profils
            </Link>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {connection === 'reconnecting' && (
              <span role="status" className="flex items-center gap-1 text-xs text-muted-foreground">
                <WifiOffIcon aria-hidden className="size-4" />
                Reconnexion…
              </span>
            )}
            <ActivityCenter />
            <ThemeMenu />
          </div>
        </div>
      </header>
      {info.data?.demo && (
        <p className="border-b bg-amber-50 px-4 py-2 text-center text-sm text-amber-950 dark:bg-amber-950 dark:text-amber-50">
          Mode démo : le module de démonstration invente des résultats, sans rien interroger.
        </p>
      )}
      <main id="main" className="mx-auto max-w-5xl px-4 py-6">
        {children}
      </main>
    </div>
  );
}

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: 'system', label: 'Comme le système' },
  { value: 'light', label: 'Clair' },
  { value: 'dark', label: 'Sombre' },
];

function ThemeMenu() {
  const { choice, resolved, setChoice } = useTheme();
  const Icon = choice === 'system' ? MonitorIcon : resolved === 'dark' ? MoonIcon : SunIcon;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Thème">
          <Icon aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuRadioGroup value={choice} onValueChange={(v) => setChoice(v as ThemeChoice)}>
          {THEMES.map((t) => (
            <DropdownMenuRadioItem key={t.value} value={t.value}>
              {t.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
