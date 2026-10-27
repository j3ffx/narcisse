// Mirrors src/narcisse/schemas.py: what the API returns and the events carry.

export type EntityKind =
  | 'identity'
  | 'name'
  | 'username'
  | 'email'
  | 'phone'
  | 'address'
  | 'domain'
  | 'organization'
  | 'account'
  | 'url'
  | 'leak'
  | 'photo';

export type SeedKind = Extract<
  EntityKind,
  'name' | 'username' | 'email' | 'phone' | 'address' | 'domain' | 'organization' | 'account'
>;

export type ProfileKind = 'personal' | 'professional' | 'mixed';
export type SeedStatus = 'watch' | 'ignore';
export type EntityStatus = 'unreviewed' | 'confirmed' | 'false_positive';
export type ScanStatus = 'running' | 'paused' | 'cancelled' | 'done';
export type RunStatus =
  'queued' | 'running' | 'paused' | 'rate_limited' | 'failed' | 'done' | 'cancelled';

export type Params = Record<string, unknown>;

export interface ProfileSettings {
  pivot_depth: number;
  modules: string[];
}

export interface Profile {
  id: number;
  name: string;
  kind: ProfileKind;
  settings: ProfileSettings;
  created_at: string;
  updated_at: string;
}

export interface Seed {
  id: number;
  profile_id: number;
  kind: SeedKind;
  value: string;
  normalized: string;
  status: SeedStatus;
  created_at: string;
}

export interface ProfileDetail extends Profile {
  seeds: Seed[];
}

export interface Run {
  id: number;
  scan_id: number;
  module: string;
  input_kind: EntityKind;
  input_value: string;
  /** 0: one of the profile's elements; more: a trace the scan followed, so many hops away. */
  depth: number;
  status: RunStatus;
  progress_done: number | null;
  progress_total: number | null;
  results_count: number;
  attempts: number;
  retry_at: string | null;
  error_code: string | null;
  error_params: Params | null;
  /** Counters the module reported ("checked", "unreachable"…). */
  notes: Record<string, number> | null;
  retryable: boolean;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
}

export interface Scan {
  id: number;
  profile_id: number;
  profile_name: string;
  status: ScanStatus;
  modules: string[];
  results_count: number;
  /** What the scan reports as a whole: traces it followed, and those left past its cap; for a
   * check, the followed request and its trace. */
  notes: { pivots?: number; capped?: number[]; check?: number; trace?: string } | null;
  created_at: string;
  finished_at: string | null;
}

export interface ScanDetail extends Scan {
  runs: Run[];
}

export interface Entity {
  id: number;
  kind: EntityKind;
  display: string;
  normalized: string;
  status: EntityStatus;
  /** Scores, 0..1: is it me, how much does it expose me (their reasons are in the detail). */
  confidence: number | null;
  risk: number | null;
  attributes: Record<string, unknown>;
}

/** One rule behind a score: a code (lib/scores.ts says it), and what it did to the score. */
export interface ScoreReason {
  code: string;
  points?: number | null;
  factor?: number | null;
  params?: Params;
}

export interface ScoreReasons {
  confidence: ScoreReason[];
  risk: ScoreReason[];
}

/** A trace that could become one of the profile's elements, and how it was found. */
export interface Lead {
  entity: Entity;
  via: Entity | null;
  relation: string | null;
}

/** How two traces relate: `source` led to `target`, according to `module`. */
export interface Edge {
  id: number;
  source_id: number;
  target_id: number;
  relation: string;
  module: string;
  confidence: number | null;
  first_seen: string;
  last_seen: string;
}

export interface GraphNode extends Entity {
  first_seen: string;
  last_seen: string;
  /** The sources that found it ("seed": declared by the user). */
  modules: string[];
  evidence_count: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: Edge[];
  /** Too many traces to send them all: the most recently seen ones came. */
  truncated: boolean;
}

export interface Evidence {
  id: number;
  scan_id: number;
  run_id: number;
  module: string;
  relation: string | null;
  url: string | null;
  excerpt: string | null;
  content_hash: string | null;
  captured_at: string;
}

export interface EntityDetail {
  entity: GraphNode;
  reasons: ScoreReasons;
  evidence: Evidence[];
  edges: Edge[];
  neighbours: Entity[];
}

/** An official page an action points to. */
export interface Guide {
  title: string;
  url: string;
}

export type Difficulty = 'easy' | 'medium' | 'hard' | 'limited' | 'impossible';

/** A site the knowledge base knows how to leave (JustDeleteMe, or Narcisse's own sheets). */
export interface Service {
  name: string;
  category: 'account' | 'broker' | 'business_directory' | 'archive' | 'keyserver';
  url: string | null;
  difficulty: Difficulty | null;
  notes: string | null;
  notes_lang: Lang;
  source: 'jdm' | 'narcisse';
}

export type Lang = 'fr' | 'en';

export interface Letter {
  subject: string;
  body: string;
}

/** One thing the user can do about a trace (lib/remediation.ts says what): Narcisse prepares
 * it, the user does it. */
export interface Action {
  code: string;
  service: Service | null;
  url: string | null;
  /** Whom to write to, when known. */
  email: string | null;
  links: Guide[];
  letter: string | null;
  letters: Partial<Record<Lang, Letter>>;
  /** The language the recipient most likely reads. */
  lang: Lang;
  /** The user follows it (À faire). */
  request: FollowedRequest | null;
}

export type RequestStatus = 'todo' | 'sent' | 'waiting' | 'done' | 'refused';

/** An action the user follows on a trace, and where it stands. */
export interface FollowedRequest {
  id: number;
  profile_id: number;
  entity: Entity;
  action: string;
  /** "" when no site is named. */
  service: string;
  letter: string | null;
  recipient: string | null;
  subject: string | null;
  body: string | null;
  status: RequestStatus;
  note: string | null;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
  reminded_at: string | null;
  closed_at: string | null;
  /** What the last scan that looked for the trace again saw. */
  check: 'gone' | 'still_there' | null;
  checked_at: string | null;
  check_scan_id: number | null;
  /** When it deserves a reminder (a month after sending), and whether that time has come. */
  reminder_at: string | null;
  due: boolean;
}

export interface ExposurePoint {
  taken_at: string;
  scan_id: number | null;
  levels: Record<string, number>;
  exposure: number;
}

/** How exposed a profile is now, how it went scan after scan, and where its requests are. */
export interface Exposure {
  levels: Record<string, number>;
  exposure: number;
  history: ExposurePoint[];
  requests: Record<RequestStatus, number>;
  due: number;
  gone: number;
}

export interface Remediation {
  actions: Action[];
  /** Where to turn when a request goes unanswered. */
  complaint: Guide;
}

/** A view of a profile's graph the user saved. Its state is the UI's (see SavedViews). */
export interface SavedView {
  id: number;
  profile_id: number;
  name: string;
  state: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Result {
  id: number;
  profile_id: number;
  scan_id: number;
  run_id: number;
  module: string;
  entity: Entity;
  edge: Edge | null;
  relation: string | null;
  confidence: number | null;
  url: string | null;
  excerpt: string | null;
  captured_at: string;
}

export interface ResultsPage {
  items: Result[];
  total: number;
}

export interface Module {
  name: string;
  title: string;
  description: string;
  category: string;
  accepts: EntityKind[];
  produces: EntityKind[];
  hosts: string[];
  /** What it contacts besides `hosts`, known only when it runs. */
  other_hosts: string;
  /** Why it can't run with the current settings (an error code), or null. */
  unavailable: string | null;
  rate_limit: { requests: number; per_seconds: number } | null;
  licence: string;
  data_source: string;
  demo: boolean;
}

export interface Activity {
  last_event_id: number;
  scans: ScanDetail[];
}

export interface AppInfo {
  version: string;
  demo: boolean;
  data_dir: string;
}

export interface RunProgress {
  run_id: number;
  scan_id: number;
  done: number;
  total: number | null;
  notes: Record<string, number> | null;
}

export interface Preferences {
  github_token_set: boolean;
  gitlab_token_set: boolean;
  exclude_adult: boolean;
  fediverse_instances: string[];
  searxng_url: string | null;
  /** Start Narcisse's SearXNG with Narcisse when it doesn't answer. */
  searxng_autostart: boolean;
}

/** The user's SearXNG: Docker present, an instance answering, and how a launch is going. */
export interface SearxngStatus {
  docker: boolean;
  address: string | null;
  running: boolean;
  state: 'idle' | 'starting' | 'ready' | 'failed';
  step: 'desktop' | 'compose' | 'waiting' | null;
  error: string | null;
}

export interface PreferencesChanges {
  github_token?: string | null;
  gitlab_token?: string | null;
  exclude_adult?: boolean;
  fediverse_instances?: string[];
  searxng_url?: string | null;
  searxng_autostart?: boolean;
}

export interface EntityUpdate extends Entity {
  profile_id: number;
}

export type LiveEvent =
  | { type: 'scan.created'; data: ScanDetail }
  | { type: 'scan.updated'; data: Scan }
  | { type: 'run.updated'; data: Run }
  | { type: 'run.progress'; data: RunProgress }
  | { type: 'result.created'; data: Result }
  | { type: 'entity.updated'; data: EntityUpdate }
  | { type: 'requests.updated'; data: { profile_id: number } };
