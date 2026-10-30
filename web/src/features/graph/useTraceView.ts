import { t } from '@/i18n';
import { NO_FILTER, passes, type TraceFilter } from '@/lib/graph';
import { useModules } from '@/lib/queries';
import type { GraphData } from '@/lib/types';
import { useCallback, useMemo, useState } from 'react';
import { useLocation, useSearch } from 'wouter';

/** What the graph and the list share: filters, "not me" shown or not. Lives in the profile page. */
export interface TraceView {
  filter: TraceFilter;
  setFilter: (filter: TraceFilter) => void;
  falsePositives: boolean;
  setFalsePositives: (shown: boolean) => void;
}

export function useTraceViewState(): TraceView {
  const [filter, setFilter] = useState<TraceFilter>(NO_FILTER);
  const [falsePositives, setFalsePositives] = useState(false);
  return { filter, setFilter, falsePositives, setFalsePositives };
}

/** The trace selected, kept in the address (`?trace=12`): a link or a reload shows it again. */
export function useSelectedTrace(): [number | null, (id: number | null) => void] {
  const search = useSearch();
  const [location, navigate] = useLocation();
  const raw = new URLSearchParams(search).get('trace');
  // Negative: a group of traces (graph view).
  const selected = raw && /^-?\d+$/.test(raw) ? Number(raw) : null;
  const select = useCallback(
    (id: number | null) => {
      navigate(id === null ? location : `${location}?trace=${id}`, { replace: true });
    },
    [location, navigate],
  );
  return [selected, select];
}

/** The ids of the traces the filter leaves out. */
export function useHidden(data: GraphData | undefined, filter: TraceFilter): Set<number> {
  return useMemo(
    () => new Set((data?.nodes ?? []).filter((n) => !passes(n, filter)).map((n) => n.id)),
    [data, filter],
  );
}

/** The modules' titles by name, for the UI ("github" → "GitHub"). */
export function useSourceTitle(): (name: string) => string {
  const modules = useModules();
  return useCallback(
    (name: string) =>
      name === 'manual'
        ? t().sourcesPage.byHand
        : (modules.data?.find((m) => m.name === name)?.title ?? name),
    [modules.data],
  );
}
