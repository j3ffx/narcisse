import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, del, get, patch, post } from './api';
import { withAnnotation } from './assistant';
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
  AiLead,
  LetterRequest,
  MachineInfo,
  ModelPull,
  Annotation,
  AnnotationTask,
  AssistantStatus,
  Triage,
  AppInfo,
  SearxngStatus,
  Diff,
  EntityDetail,
  Exposure,
  FollowedRequest,
  Lang,
  Letter,
  RequestStatus,
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
  Remediation,
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
  searxng: ['searxng'] as const,
  graph: (profileId: number, falsePositives: boolean) =>
    ['graph', profileId, falsePositives] as const,
  graphs: (profileId: number) => ['graph', profileId] as const,
  entity: (id: number) => ['entity', id] as const,
  views: (profileId: number) => ['views', profileId] as const,
  leads: (profileId: number) => ['leads', profileId] as const,
  entities: ['entity'] as const,
  remediation: (id: number) => ['remediation', id] as const,
  requests: (profileId: number) => ['requests', profileId] as const,
  exposure: (profileId: number) => ['exposure', profileId] as const,
  assistant: ['assistant'] as const,
  annotations: (entityId: number) => ['annotations', entityId] as const,
  triage: (profileId: number) => ['triage', profileId] as const,
  aiLeads: (profileId: number) => ['ai-leads', profileId] as const,
  pull: ['model-pull'] as const,
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

/** What the user can do about a trace, and the requests Narcisse prepares for it. */
export const useRemediation = (id: number) =>
  useQuery({
    queryKey: keys.remediation(id),
    queryFn: () => get<Remediation>(`/entities/${id}/remediation`),
  });

/** What changed between two of the profile's scans. */
export const useDiff = (profileId: number, before: number | null, after: number | null) =>
  useQuery({
    queryKey: ['diff', profileId, before, after],
    queryFn: () => get<Diff>(`/profiles/${profileId}/diff?before=${before}&after=${after}`),
    enabled: before !== null && after !== null,
  });

/** The actions the user follows on a profile's traces. */
export const useRequests = (profileId: number) =>
  useQuery({
    queryKey: keys.requests(profileId),
    queryFn: () => get<FollowedRequest[]>(`/profiles/${profileId}/requests`),
  });

export const useExposure = (profileId: number) =>
  useQuery({
    queryKey: keys.exposure(profileId),
    queryFn: () => get<Exposure>(`/profiles/${profileId}/exposure`),
  });

/** The reminder of a sent request (loaded when the user asks for it). */
export const useReminder = (requestId: number, enabled: boolean) =>
  useQuery({
    queryKey: ['reminder', requestId],
    queryFn: () => get<Partial<Record<Lang, Letter>>>(`/requests/${requestId}/reminder`),
    enabled,
    staleTime: 0,
  });

function requestsChanged(client: QueryClient, profileId: number) {
  void client.invalidateQueries({ queryKey: keys.requests(profileId) });
  void client.invalidateQueries({ queryKey: keys.exposure(profileId) });
  void client.invalidateQueries({ queryKey: ['remediation'] });
}

export interface FollowBody {
  action: string;
  service?: string;
  letter?: string | null;
  recipient?: string | null;
  subject?: string | null;
  body?: string | null;
  status?: RequestStatus;
}

/** Follows an action of a trace's sheet (or updates the one followed). */
export function useFollowAction(entityId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: FollowBody) => post<FollowedRequest>(`/entities/${entityId}/requests`, body),
    onSuccess: (request) => requestsChanged(client, request.profile_id),
    onError: failed,
  });
}

export function useUpdateRequest(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number;
      status?: RequestStatus;
      note?: string;
      recipient?: string;
      reminded?: boolean;
    }) => patch<FollowedRequest>(`/requests/${id}`, body),
    onSuccess: () => requestsChanged(client, profileId),
    onError: failed,
  });
}

export function useStopFollowing(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => del(`/requests/${id}`),
    onSuccess: () => requestsChanged(client, profileId),
    onError: failed,
  });
}

/** Runs again the searches that found the trace: their end says whether it is gone. */
export function useCheckRequest() {
  return useMutation({
    mutationFn: (id: number) => post<ScanDetail>(`/requests/${id}/check`),
    onError: failed,
  });
}

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
    onSuccess: (profile, body) => {
      client.setQueryData(keys.profile(id), profile);
      void client.invalidateQueries({ queryKey: keys.profiles });
      if (body.kind) {
        // A professional profile weighs what it expects in public less: every score may change.
        void client.invalidateQueries({ queryKey: keys.graphs(id) });
        void client.invalidateQueries({ queryKey: keys.entities });
        void client.invalidateQueries({ queryKey: ['remediation'] });
        void client.invalidateQueries({ queryKey: keys.allResults });
        void client.invalidateQueries({ queryKey: keys.leads(id) });
      }
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
      void client.invalidateQueries({ queryKey: keys.aiLeads(profileId) });
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

/** The SearXNG status; polled while a launch asked from the app is under way. */
export function useSearxng() {
  return useQuery({
    queryKey: keys.searxng,
    queryFn: () => get<SearxngStatus>('/searxng'),
    refetchInterval: (query) => (query.state.data?.state === 'starting' ? 2000 : false),
  });
}

/** Installs (if needed) and starts the user's SearXNG, opening Docker Desktop when it isn't up. */
export function useStartSearxng() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => post<SearxngStatus>('/searxng/start'),
    onSuccess: (status) => client.setQueryData(keys.searxng, status),
    onError: failed,
  });
}

export function useUpdatePreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: PreferencesChanges) => patch<Preferences>('/preferences', changes),
    onSuccess: (preferences) => {
      client.setQueryData(keys.preferences, preferences);
      void client.invalidateQueries({ queryKey: keys.assistant });
    },
    onError: failed,
  });
}

// The assistant

/** The assistant the user chose, and whether it can answer now. */
export const useAssistant = () =>
  useQuery({ queryKey: keys.assistant, queryFn: () => get<AssistantStatus>('/assistant') });

/** A neutral question (no data sent), to see that the assistant answers. */
export function useTryAssistant() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => post<{ model: string | null }>('/assistant/try'),
    onSettled: () => void client.invalidateQueries({ queryKey: keys.assistant }),
    onError: failed,
  });
}

export const useAnnotations = (entityId: number, enabled = true) =>
  useQuery({
    queryKey: keys.annotations(entityId),
    queryFn: () => get<Annotation[]>(`/entities/${entityId}/annotations`),
    enabled,
  });

/** What asking about a trace would send (fetched when the user opens it). */
export const usePrompt = (entityId: number, task: AnnotationTask, enabled: boolean) =>
  useQuery({
    queryKey: ['prompt', entityId, task],
    queryFn: () => get<{ text: string }>(`/entities/${entityId}/prompt?task=${task}`),
    enabled,
  });

/** Asks the assistant about a trace; its answer arrives as a live event. */
export function useAsk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, task }: { entityId: number; task: AnnotationTask }) =>
      post<Annotation>(`/entities/${entityId}/annotations`, { task }),
    onSuccess: (annotation) => annotated(client, annotation),
    onError: failed,
  });
}

export function useUpdateAnnotation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...changes
    }: {
      id: number;
      decision?: Annotation['decision'];
      output?: Record<string, unknown>;
    }) => patch<Annotation>(`/annotations/${id}`, changes),
    onSuccess: (annotation) => annotated(client, annotation),
    onError: failed,
  });
}

export function useDeleteAnnotation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (annotation: Annotation) => del(`/annotations/${annotation.id}`),
    onSuccess: (_, annotation) => unannotated(client, annotation.entity_id, annotation.id),
    onError: failed,
  });
}

/** How many traces a batch of "is it me?" questions would ask about. */
export const useTriageCount = (profileId: number, enabled: boolean) =>
  useQuery({
    queryKey: keys.triage(profileId),
    queryFn: () => get<Triage>(`/profiles/${profileId}/triage`),
    enabled,
  });

export function useTriage(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => post<Triage>(`/profiles/${profileId}/triage`),
    onSettled: () => void client.invalidateQueries({ queryKey: keys.triage(profileId) }),
    onError: failed,
  });
}

/** What this machine can run, and the model servers running (read when the user looks). */
export const useMachine = (enabled: boolean) =>
  useQuery({
    queryKey: ['machine'],
    queryFn: () => get<MachineInfo>('/assistant/machine'),
    enabled,
    staleTime: 10_000,
  });

/** A model Ollama downloads; polled while it runs. */
export const useModelPull = () =>
  useQuery({
    queryKey: keys.pull,
    queryFn: () => get<ModelPull>('/assistant/pull'),
    refetchInterval: (query) => (query.state.data?.status === 'pulling' ? 1000 : false),
  });

export function useStartPull() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (model: string) => post<ModelPull>('/assistant/pull', { model }),
    onSuccess: (pull) => client.setQueryData(keys.pull, pull),
    onError: failed,
  });
}

export function useCancelPull() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<ModelPull>('DELETE', '/assistant/pull'),
    onSuccess: (pull) => client.setQueryData(keys.pull, pull),
    onError: failed,
  });
}

/** Has the assistant adapt a letter; its proposal arrives as a live event. */
export function useAdaptLetter(entityId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (letter: LetterRequest) => post<Annotation>(`/entities/${entityId}/letter`, letter),
    onSuccess: (annotation) => annotated(client, annotation),
    onError: failed,
  });
}

/** What adapting a letter would send: the profile's identity behind markers. */
export const useLetterPrompt = (entityId: number) =>
  useMutation({
    mutationFn: (letter: LetterRequest) =>
      post<{ text: string }>(`/entities/${entityId}/letter/prompt`, letter),
    onError: failed,
  });

/** The elements the assistant read in the profile's traces, not declared yet. */
export const useAiLeads = (profileId: number, enabled: boolean) =>
  useQuery({
    queryKey: keys.aiLeads(profileId),
    queryFn: () => get<AiLead[]>(`/profiles/${profileId}/ai-leads`),
    enabled,
  });

export function useDismissAiLead(profileId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (lead: AiLead) =>
      post<Annotation>(`/annotations/${lead.annotation_id}/leads/${lead.index}/dismiss`),
    onMutate: (lead) => {
      client.setQueryData<AiLead[]>(keys.aiLeads(profileId), (leads) =>
        leads?.filter((l) => l !== lead),
      );
    },
    onSuccess: (annotation) => annotated(client, annotation),
    onError: (error) => {
      void client.invalidateQueries({ queryKey: keys.aiLeads(profileId) });
      failed(error);
    },
  });
}

/** An annotation, new or changed, in its trace's list. */
export function annotated(client: QueryClient, annotation: Annotation) {
  client.setQueryData<Annotation[]>(keys.annotations(annotation.entity_id), (list) =>
    list ? withAnnotation(list, annotation) : list,
  );
}

export function unannotated(client: QueryClient, entityId: number, id: number) {
  client.setQueryData<Annotation[]>(keys.annotations(entityId), (list) =>
    list ? list.filter((a) => a.id !== id) : list,
  );
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
  // What to do about it follows its status (nothing, once it isn't the user's).
  void client.invalidateQueries({ queryKey: keys.remediation(entity.id) });
}
