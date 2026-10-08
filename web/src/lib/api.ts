import type { Params } from './types';

/** An error the UI can explain: the server's code and parameters (see lib/errors.ts). */
export class ApiError extends Error {
  readonly code: string;
  readonly params: Params;
  readonly status: number;

  constructor(code: string, params: Params = {}, status = 0) {
    super(code);
    this.code = code;
    this.params = params;
    this.status = status;
  }
}

export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError('offline');
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (data ?? {}) as { code?: string; params?: Params };
    throw new ApiError(error.code ?? 'internal_error', error.params ?? {}, response.status);
  }
  return data as T;
}

export const get = <T>(path: string) => api<T>('GET', path);
export const post = <T>(path: string, body: unknown = {}) => api<T>('POST', path, body);
export const patch = <T>(path: string, body: unknown) => api<T>('PATCH', path, body);
export const del = (path: string) => api<void>('DELETE', path);
