import { lazy, t } from '@/i18n';
import type {
  EntityKind,
  EntityStatus,
  ProfileKind,
  RunStatus,
  ScanStatus,
  SeedKind,
} from './types';

export const KIND_LABELS: Record<EntityKind, string> = lazy(() => t().kinds);

export const SEED_KINDS: SeedKind[] = [
  'name',
  'username',
  'email',
  'phone',
  'address',
  'domain',
  'organization',
  'account',
];

export const SEED_EXAMPLES: Record<SeedKind, string> = lazy(() => t().seedExamples);

export const PROFILE_KIND_LABELS: Record<ProfileKind, string> = lazy(() => t().profileKinds);

export const ENTITY_STATUS_LABELS: Record<EntityStatus, string> = lazy(() => t().entityStatus);

export const SCAN_STATUS_LABELS: Record<ScanStatus, string> = lazy(() => t().scanStatus);

export const RUN_STATUS_LABELS: Record<RunStatus, string> = lazy(() => t().runStatus);

export const RELATION_LABELS: Record<string, string> = lazy(() => t().relations);

export const noteLabels = (): [string, (n: number) => string][] => t().runNotes;

export const CATEGORY_LABELS: Record<string, string> = lazy(() => t().categories);

export const FINISHED_RUN: ReadonlySet<RunStatus> = new Set(['failed', 'done', 'cancelled']);
export const ACTIVE_SCAN: ReadonlySet<ScanStatus> = new Set(['running', 'paused']);
