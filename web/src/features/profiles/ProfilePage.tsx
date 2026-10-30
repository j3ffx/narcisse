import { t } from '@/i18n';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Pending } from '@/components/Pending';
import { SearxngDown } from '@/components/SearxngDown';
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
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { ScanStatusBadge } from '@/features/scans/status';
import { errorMessage, messageFor } from '@/lib/errors';
import { KIND_LABELS, PROFILE_KIND_LABELS } from '@/lib/labels';
import {
  useDeleteProfile,
  useExposure,
  useModules,
  useProfile,
  useScans,
  useStartScan,
} from '@/lib/queries';
import { formatDate } from '@/lib/time';
import type { ProfileDetail } from '@/lib/types';
import { RadarIcon, Trash2Icon } from 'lucide-react';
import { lazy, Suspense, useState } from 'react';
import { Link, useLocation } from 'wouter';
import { useTraceViewState } from '@/features/graph/useTraceView';
import { cn } from 'cn';
import { AssistedSearch } from '@/features/search/AssistedSearch';
import { Leads, PivotDepth, RescanSetting } from './Leads';
import { ExportMenu } from './ExportMenu';
import { TriageButton } from '@/features/assistant/TriageButton';
import { Requests } from './Requests';
import { ScanDiff } from '@/features/scans/ScanDiff';
import { SeedsEditor } from './SeedsEditor';
import { tabs, type ProfileTab } from './tabs';

// The graph's code (WebGL, layout) loads only when a profile's traces are shown.
const GraphView = lazy(() =>
  import('@/features/graph/GraphView').then((m) => ({ default: m.GraphView })),
);
const TraceList = lazy(() =>
  import('@/features/graph/TraceList').then((m) => ({ default: m.TraceList })),
);

export function ProfilePage({ id, tab }: { id: number; tab: ProfileTab }) {
  const profile = useProfile(id);
  const view = useTraceViewState();
  const due = useExposure(id).data?.due;
  if (profile.isPending) return <Pending label={t().profile.loading} />;
  if (profile.isError) return <p role="alert">{errorMessage(profile.error)}</p>;
  const data = profile.data;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            <Link href="/" className="hover:underline">
              {t().shell.profiles}
            </Link>{' '}
            · {PROFILE_KIND_LABELS[data.kind]}
          </p>
          <h1 className="font-heading text-2xl font-semibold">{data.name}</h1>
        </div>
        <div className="flex gap-2">
          <StartScanDialog profile={data} />
          <TriageButton profileId={id} />
          <ExportMenu profileId={id} />
          <DeleteProfile id={id} name={data.name} />
        </div>
      </div>
      <nav aria-label={t().profile.views} className="flex gap-1 border-b">
        {tabs().map(([key, title]) => (
          <Link
            key={key}
            href={key === 'graphe' ? `/profils/${id}` : `/profils/${id}/${key}`}
            aria-current={key === tab ? 'page' : undefined}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-sm',
              key === tab
                ? 'border-primary font-medium text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {title}
            {key === 'a-faire' && !!due && (
              <span className="ml-1.5 rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
                {due}
                <span className="sr-only"> {t().profile.toRemind}</span>
              </span>
            )}
          </Link>
        ))}
      </nav>
      <ErrorBoundary
        key={tab}
        label={tab === 'graphe' ? t().profile.theGraph : t().profile.thisView}
      >
        <Suspense fallback={<Pending label={t().profile.loadingView} />}>
          {tab === 'graphe' && <GraphView profileId={id} view={view} />}
          {tab === 'liste' && <TraceList profileId={id} view={view} />}
        </Suspense>
      </ErrorBoundary>
      {tab === 'elements' && (
        <div className="grid gap-8">
          <SeedsEditor profileId={id} seeds={data.seeds} />
          <Leads profileId={id} />
          <PivotDepth profile={data} />
          <RescanSetting profile={data} />
        </div>
      )}
      {tab === 'recherche' && <AssistedSearch profileId={id} seeds={data.seeds} />}
      {tab === 'a-faire' && <Requests profileId={id} />}
      {tab === 'scans' && <ScanHistory profileId={id} />}
    </div>
  );
}

function StartScanDialog({ profile }: { profile: ProfileDetail }) {
  const modules = useModules();
  const start = useStartScan(profile.id);
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<string[] | null>(null);
  const [, navigate] = useLocation();
  const watched = profile.seeds.filter((s) => s.status === 'watch');
  const kinds = new Set(watched.map((s) => s.kind));
  const usable = (modules.data ?? []).filter((m) => m.accepts.some((k) => kinds.has(k as never)));
  // A source the settings don't let run is shown, unticked, with what it needs.
  const ready = usable.filter((m) => m.unavailable === null);
  const selected = (chosen ?? ready.map((m) => m.name)).filter((name) =>
    ready.some((m) => m.name === name),
  );

  const launch = () =>
    start.mutate(selected, {
      onSuccess: (scan) => {
        setOpen(false);
        navigate(`/scans/${scan.id}`);
      },
    });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setChosen(null);
          start.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button disabled={watched.length === 0}>
          <RadarIcon aria-hidden />
          {t().scan.start}
        </Button>
      </DialogTrigger>
      {/* The sources scroll; the title and the button to start stay in view. */}
      <DialogContent className="grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t().scan.start}</DialogTitle>
          <DialogDescription>{t().scan.watched(watched.length)}</DialogDescription>
        </DialogHeader>
        <div className="-mx-4 grid content-start gap-3 overflow-y-auto px-4">
          {modules.isPending && <Pending label={t().scan.loadingSources} />}
          {modules.data && usable.length === 0 && (
            <p className="text-sm text-muted-foreground">{t().scan.noSource}</p>
          )}
          <ul className="grid gap-3">
            {usable.map((module) => {
              const id = `module-${module.name}`;
              return (
                <li key={module.name} className="flex gap-3">
                  <Checkbox
                    id={id}
                    disabled={module.unavailable !== null}
                    aria-describedby={module.unavailable ? `${id}-needs` : undefined}
                    checked={selected.includes(module.name)}
                    onCheckedChange={(checked) =>
                      setChosen(
                        checked
                          ? [...selected, module.name]
                          : selected.filter((n) => n !== module.name),
                      )
                    }
                  />
                  <div className="grid gap-0.5">
                    <Label htmlFor={id}>
                      {module.title}
                      {module.demo && (
                        <span className="rounded bg-amber-100 px-1.5 text-xs text-amber-950 dark:bg-amber-950 dark:text-amber-50">
                          {t().scan.fake}
                        </span>
                      )}
                    </Label>
                    <p className="text-sm text-muted-foreground">{module.description}</p>
                    {module.name === 'searxng' && !module.unavailable && <SearxngDown />}
                    {module.unavailable && (
                      <p id={`${id}-needs`} className="text-sm">
                        {messageFor(module.unavailable)}{' '}
                        <Link href="/reglages" className="underline underline-offset-2">
                          {t().shell.settings}
                        </Link>
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {t().scan.accepts}{' '}
                      {module.accepts
                        .filter((k) => kinds.has(k as never))
                        .map((k) => KIND_LABELS[k])
                        .join(', ')}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
          {start.isError && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-300">
              {errorMessage(start.error)}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button onClick={launch} disabled={start.isPending || selected.length === 0}>
            {start.isPending ? t().scan.starting : t().scan.go}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteProfile({ id, name }: { id: number; name: string }) {
  const remove = useDeleteProfile(id);
  const [, navigate] = useLocation();
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t().profile.delete}>
          <Trash2Icon aria-hidden />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t().profile.deleteTitle(name)}</AlertDialogTitle>
          <AlertDialogDescription>{t().profile.deleteText}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t().profile.keep}</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => remove.mutate(undefined, { onSuccess: () => navigate('/') })}
          >
            {t().common.delete}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ScanHistory({ profileId }: { profileId: number }) {
  const scans = useScans(profileId);
  return (
    <section aria-labelledby="scans-title" className="grid gap-3">
      <h2 id="scans-title" className="font-heading text-lg font-semibold">
        {t().tabs.scans}
      </h2>
      {scans.isPending && <Pending label={t().profile.loadingScans} />}
      {scans.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">{t().profile.noScan}</p>
      )}
      {scans.data && <ScanDiff profileId={profileId} scans={scans.data} />}
      <ul className="divide-y rounded-lg border empty:hidden">
        {scans.data?.map((scan) => (
          <li key={scan.id}>
            <Link
              href={`/scans/${scan.id}`}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 hover:bg-muted/50"
            >
              <span>
                {formatDate(scan.created_at)}
                {scan.notes?.check ? ` · ${t().profile.checkOf(String(scan.notes.trace))}` : ''}
                {scan.notes?.scheduled ? ` · ${t().profile.scheduled}` : ''}
              </span>
              <span className="flex items-center gap-3 text-sm text-muted-foreground">
                {t().scan.results(scan.results_count)}
                <ScanStatusBadge status={scan.status} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
