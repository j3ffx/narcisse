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
  status: RunStatus;
  progress_done: number | null;
  progress_total: number | null;
  results_count: number;
  attempts: number;
  retry_at: string | null;
  error_code: string | null;
  error_params: Params | null;
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
  confidence: number | null;
}

export interface Result {
  id: number;
  scan_id: number;
  run_id: number;
  module: string;
  entity: Entity;
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
  intrusion: 'passive' | 'light_active';
  hosts: string[];
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
}

export type LiveEvent =
  | { type: 'scan.created'; data: ScanDetail }
  | { type: 'scan.updated'; data: Scan }
  | { type: 'run.updated'; data: Run }
  | { type: 'run.progress'; data: RunProgress }
  | { type: 'result.created'; data: Result };
