import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { del, get, patch, post } from './api';
import { errorMessage } from './errors';
import { withEntity as withEntityInGraph } from './graph';
import {
  cancelled,
  inActivity,
  paused,
  resumed,
  retried,
  withEntity,
  type ResultFilter,
} from './live';
import type {
  Activity,
  AppInfo,
  EntityDetail,
  GraphData,
  Lead,
  SavedView,
  Module,
  Profile,
  ProfileDetail,
  Entity,
  EntityStatus,
  Preferences,
  PreferencesChanges,
  ProfileKind,
  ProfileSettings,
  ResultsPage,
  Scan,
  ScanDetail,
  Seed,
  SeedKind,
  SeedStatus,
} from './types';

export const keys = {
  info: ['info'] as const,
  modules: ['modules'] as const,
  activity: ['activity'] as const,
  profiles: ['profiles'] as const,
  profile: (id: number) => ['profile', id] as const,
  scans: (profileId: number) => ['scans', profileId] as const,
  scan: (id: number) => ['scan', id] as const,
  results: (scanId: number) => ['results', scanId] as const,
  filteredResults: (scanId: number, filter: ResultFilter) => ['results', scanId, filter] as const,
  allResults: ['results'] as const,
  preferences: ['preferences'] as const,
  graph: (profileId: number, falsePositives: boolean) =>
    ['graph', profileId, falsePositives] as const,
  graphs: (profileId: number) => ['graph', profileId] as const,
  entity: (id: number) => ['entity', id] as const,
  views: (profileId: number) => ['views', profileId] as const,
  leads: (profileId: number) => ['leads', profileId] as const,
  entities: ['entity'] as const,
};

// Reads

export const useInfo = () =>
  useQuery({ queryKey: keys.info, queryFn: () => get<AppInfo>('/info') });

export const useModules = () =>
  useQuery({ queryKey: keys.modules, queryFn: () => get<Module[]>('/modules') });

export const useProfiles = () =>
  useQuery({ queryKey: keys.profiles, queryFn: () => get<Profile[]>('/profiles') });

export const useProfile = (id: number) =>
  useQuery({ queryKey: keys.profile(id), queryFn: () => get<ProfileDetail>(`/profiles/${id}`) });

export const useGraph = (profileId: number, falsePositives: boolean) =>
  useQuery({
    queryKey: keys.graph(profileId, falsePositives),
    queryFn: () =>
      get<GraphData>(
        `/profiles/${profileId}/graph${falsePositives ? '?false_positives=true' : ''}`,
      ),
  });

export const useEntityDetail = (id: number | null) =>
  useQuery({
    queryKey: keys.entity(id ?? 0),
    queryFn: () => get<EntityDetail>(`/entities/${id}`),
    enabled: id !== null,
  });

/** Traces sure enough to search from that aren't elements yet. */
export const useLeads = (profileId: number) =>
  useQuery({
    queryKey: keys.leads(profileId),
    queryFn: () => get<Lead[]>(`/profiles/${profileId}/leads`),
  });

/** Stops suggesting a trace as a new element. */
export function useDismissLead(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (entityId: number) =>
      patch<Entity>(`/entities/${entityId}`, { pivot_dismissed: true }),
    onMutate: (entityId) => {
      const previous = client.getQueryData<Lead[]>(keys.leads(profileId));
      if (previous)
        client.setQueryData(
          keys.leads(profileId),
          previous.filter((lead) => lead.entity.id !== entityId),
        );
      return previous;
    },
    onError: (error, _id, previous) => {
      if (previous) client.setQueryData(keys.leads(profileId), previous);
      failed(error);
    },
  });
}

export const useSavedViews = (profileId: number) =>
  useQuery({
    queryKey: keys.views(profileId),
    queryFn: () => get<SavedView[]>(`/profiles/${profileId}/views`),
  });

export function useSaveView(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (view: { name: string; state: Record<string, unknown> }) =>
      post<SavedView>(`/profiles/${profileId}/views`, view),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.views(profileId) }),
    onError: failed,
  });
}

export function useDeleteView(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => del(`/views/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.views(profileId) }),
    onError: failed,
  });
}

export function useMakeDemoGraph() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (nodes: number) => post<{ profile_id: number }>('/demo/graph', { nodes }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.profiles }),
    onError: failed,
  });
}

export const useScans = (profileId: number) =>
  useQuery({
    queryKey: keys.scans(profileId),
    queryFn: () => get<Scan[]>(`/profiles/${profileId}/scans`),
  });

export const useScan = (id: number) =>
  useQuery({ queryKey: keys.scan(id), queryFn: () => get<ScanDetail>(`/scans/${id}`) });

/** Filled by the live connection (hooks/useLiveUpdates.ts), never fetched on its own. */
export const useActivity = () =>
  useQuery<Activity>({
    queryKey: keys.activity,
    queryFn: () => get<Activity>('/activity'),
    enabled: false,
  });

export const RESULTS_PAGE = 500;

export const useResults = (scanId: number, filter: ResultFilter) =>
  useQuery({
    queryKey: keys.filteredResults(scanId, filter),
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(RESULTS_PAGE) });
      if (filter.kind) params.set('kind', filter.kind);
      if (filter.q.trim()) params.set('q', filter.q.trim());
      if (filter.falsePositives) params.set('false_positives', 'true');
      return get<ResultsPage>(`/scans/${scanId}/results?${params}`);
    },
    placeholderData: (previous) => previous,
  });

// Profiles and seeds

const failed = (error: unknown) => {
  toast.error(errorMessage(error));
};

export function useCreateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; kind: ProfileKind }) =>
      post<ProfileDetail>('/profiles', body),
    onSuccess: (profile) => {
      client.setQueryData(keys.profile(profile.id), profile);
      void client.invalidateQueries({ queryKey: keys.profiles });
    },
  });
}

export function useUpdateProfile(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; kind?: ProfileKind; settings?: ProfileSettings }) =>
      patch<ProfileDetail>(`/profiles/${id}`, body),
    onSuccess: (profile) => {
      client.setQueryData(keys.profile(id), profile);
      void client.invalidateQueries({ queryKey: keys.profiles });
    },
    onError: failed,
  });
}

export function useDeleteProfile(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => del(`/profiles/${id}`),
    onSuccess: () => {
      client.removeQueries({ queryKey: keys.profile(id) });
      void client.invalidateQueries({ queryKey: keys.profiles });
    },
    onError: failed,
  });
}

export function useAddSeed(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { kind: SeedKind; value: string }) =>
      post<Seed>(`/profiles/${profileId}/seeds`, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.profile(profileId) });
      void client.invalidateQueries({ queryKey: keys.leads(profileId) });
    },
  });
}

/** A page the user found themselves, added to their traces. */
export function useAddTrace(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { url: string; note: string }) =>
      post<Entity>(`/profiles/${profileId}/traces`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.graphs(profileId) }),
  });
}

export function useUpdateSeed(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: SeedStatus }) =>
      patch<Seed>(`/seeds/${id}`, { status }),
    onMutate: ({ id, status }) =>
      setSeeds(client, profileId, (seeds) =>
        seeds.map((s) => (s.id === id ? { ...s, status } : s)),
      ),
    onError: (error, _vars, previous) => {
      if (previous) client.setQueryData(keys.profile(profileId), previous);
      failed(error);
    },
    onSettled: () => client.invalidateQueries({ queryKey: keys.profile(profileId) }),
  });
}

export function useDeleteSeed(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => del(`/seeds/${id}`),
    onMutate: (id) => setSeeds(client, profileId, (seeds) => seeds.filter((s) => s.id !== id)),
    onError: (error, _id, previous) => {
      if (previous) client.setQueryData(keys.profile(profileId), previous);
      failed(error);
    },
    onSettled: () => client.invalidateQueries({ queryKey: keys.profile(profileId) }),
  });
}

function setSeeds(client: QueryClient, profileId: number, change: (seeds: Seed[]) => Seed[]) {
  const previous = client.getQueryData<ProfileDetail>(keys.profile(profileId));
  if (previous) {
    client.setQueryData(keys.profile(profileId), { ...previous, seeds: change(previous.seeds) });
  }
  return previous;
}

// Scans

export function useStartScan(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (modules: string[]) =>
      post<ScanDetail>(`/profiles/${profileId}/scans`, { modules }),
    onSuccess: (scan) => {
      client.setQueryData(keys.scan(scan.id), scan);
      client.setQueryData<Activity>(keys.activity, (activity) =>
        activity ? inActivity(activity, scan.id, (s) => s, scan) : activity,
      );
      void client.invalidateQueries({ queryKey: keys.scans(profileId) });
    },
  });
}

/** Shows a command's effect at once, and puts things back if the server refuses it. */
function useScanCommand(path: (id: number) => string, change: (s: ScanDetail) => ScanDetail) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (scanId: number) => post<void>(path(scanId)),
    onMutate: (scanId) => applyToScan(client, scanId, change),
    onError: (error, _id, previous) => {
      restore(client, previous);
      failed(error);
    },
  });
}

export const usePauseScan = () => useScanCommand((id) => `/scans/${id}/pause`, paused);
export const useResumeScan = () => useScanCommand((id) => `/scans/${id}/resume`, resumed);
export const useCancelScan = () => useScanCommand((id) => `/scans/${id}/cancel`, cancelled);

export function useRetryRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ runId }: { scanId: number; runId: number }) =>
      post<void>(`/runs/${runId}/retry`),
    onMutate: ({ scanId, runId }) => applyToScan(client, scanId, (s) => retried(s, runId)),
    onError: (error, _vars, previous) => {
      restore(client, previous);
      failed(error);
    },
  });
}

interface Previous {
  scanId: number;
  scan: ScanDetail | undefined;
  activity: Activity | undefined;
}

function applyToScan(
  client: QueryClient,
  scanId: number,
  change: (s: ScanDetail) => ScanDetail,
): Previous {
  const previous = {
    scanId,
    scan: client.getQueryData<ScanDetail>(keys.scan(scanId)),
    activity: client.getQueryData<Activity>(keys.activity),
  };
  if (previous.scan) client.setQueryData(keys.scan(scanId), change(previous.scan));
  if (previous.activity) {
    client.setQueryData(keys.activity, inActivity(previous.activity, scanId, change));
  }
  return previous;
}

function restore(client: QueryClient, previous: Previous | undefined) {
  if (!previous) return;
  if (previous.scan) client.setQueryData(keys.scan(previous.scanId), previous.scan);
  if (previous.activity) client.setQueryData(keys.activity, previous.activity);
}

// Reviewing traces

/** "It's me", "not me", or back to "not sure": every list showing the trace follows at once. */
export function useReviewEntity() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ entity, status }: { entity: Entity; status: EntityStatus }) =>
      patch<Entity>(`/entities/${entity.id}`, { status }),
    onMutate: ({ entity, status }) => {
      const previous = [
        ...client.getQueriesData({ queryKey: keys.allResults }),
        ...client.getQueriesData({ queryKey: ['graph'] }),
        ...client.getQueriesData({ queryKey: keys.entities }),
      ];
      reviewed(client, { ...entity, status });
      return previous;
    },
    onError: (error, _vars, previous) => {
      for (const [key, data] of previous ?? []) client.setQueryData(key, data);
      failed(error);
    },
  });
}

// Settings

export const usePreferences = () =>
  useQuery({ queryKey: keys.preferences, queryFn: () => get<Preferences>('/preferences') });

export function useUpdatePreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: PreferencesChanges) => patch<Preferences>('/preferences', changes),
    onSuccess: (preferences) => client.setQueryData(keys.preferences, preferences),
    onError: failed,
  });
}

/** A trace's new status and scores, everywhere the cache shows it. */
export function reviewed(client: QueryClient, entity: Entity) {
  client.setQueriesData<ResultsPage>({ queryKey: keys.allResults }, (page) =>
    page ? withEntity(page, entity) : page,
  );
  for (const [key, graph] of client.getQueriesData<GraphData>({ queryKey: ['graph'] })) {
    if (graph) client.setQueryData(key, withEntityInGraph(graph, entity, key[2] === true));
  }
  client.setQueriesData<EntityDetail>({ queryKey: keys.entities }, (detail) =>
    detail && detail.entity.id === entity.id
      ? {
          ...detail,
          entity: {
            ...detail.entity,
            status: entity.status,
            confidence: entity.confidence,
            risk: entity.risk,
          },
        }
      : detail,
  );
}
