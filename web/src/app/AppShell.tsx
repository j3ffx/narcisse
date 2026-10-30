import { t } from '@/i18n';
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
import { Link, useLocation } from 'wouter';
import { cn } from 'cn';
import { useTheme, type ThemeChoice } from './theme';

export function AppShell({
  connection,
  children,
}: {
  connection: Connection;
  children: ReactNode;
}) {
  const info = useInfo();
  const [location] = useLocation();
  // A profile's pages take the whole width (all its tabs alike: switching doesn't move them).
  const wide = /^\/profils\/\d+(\/|$)/.test(location);
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-background focus:px-3 focus:py-2"
      >
        {t().shell.skip}
      </a>
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
        <div
          className={cn(
            'mx-auto flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5',
            wide ? 'max-w-[110rem]' : 'max-w-5xl',
          )}
        >
          <Link href="/" className="flex items-center gap-2 font-heading text-lg font-semibold">
            <img src="/favicon.svg" alt="" className="size-6" />
            Narcisse
          </Link>
          <nav
            aria-label={t().shell.navigation}
            className="order-last flex w-full gap-4 text-sm sm:order-none sm:ml-2 sm:w-auto"
          >
            {[
              ['/', t().shell.profiles],
              ['/sources', t().shell.sources],
              ['/mot-de-passe', t().shell.password],
              ['/reglages', t().shell.settings],
            ].map(([href, label]) => (
              <Link
                key={href}
                href={href!}
                className={(active) =>
                  active
                    ? 'font-medium text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }
              >
                {label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {connection === 'reconnecting' && (
              <span role="status" className="flex items-center gap-1 text-xs text-muted-foreground">
                <WifiOffIcon aria-hidden className="size-4" />
                {t().shell.reconnecting}
              </span>
            )}
            <ActivityCenter />
            <ThemeMenu />
          </div>
        </div>
      </header>
      {info.data?.demo && (
        <p className="border-b bg-amber-50 px-4 py-2 text-center text-sm text-amber-950 dark:bg-amber-950 dark:text-amber-50">
          {t().shell.demoBanner}
        </p>
      )}
      <main id="main" className={cn('mx-auto px-4 py-6', wide ? 'max-w-[110rem]' : 'max-w-5xl')}>
        {children}
      </main>
    </div>
  );
}

const THEMES: ThemeChoice[] = ['system', 'light', 'dark'];

function ThemeMenu() {
  const { choice, resolved, setChoice } = useTheme();
  const Icon = choice === 'system' ? MonitorIcon : resolved === 'dark' ? MoonIcon : SunIcon;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t().shell.theme}>
          <Icon aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuRadioGroup value={choice} onValueChange={(v) => setChoice(v as ThemeChoice)}>
          {THEMES.map((theme) => (
            <DropdownMenuRadioItem key={theme} value={theme}>
              {t().shell.themes[theme]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
