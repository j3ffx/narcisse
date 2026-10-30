import { ApiError } from './api';
import { t } from '@/i18n';
import type { Params } from './types';

/** The sentence shown for an error code (the server never sends text, only codes). */
export function messageFor(code: string, params: Params = {}): string {
  return t().errors[code]?.(params) ?? t().unexpectedError(code);
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? messageFor(error.code, error.params)
    : messageFor('internal_error');
}
