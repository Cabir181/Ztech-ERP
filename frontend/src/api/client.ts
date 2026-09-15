/**
 * The single place the interface talks to the API.
 *
 * Everything goes through `request`, so CSRF handling, the error envelope and
 * the stale-record conflict are dealt with once rather than in every screen.
 * The frontend is a convenience layer: the server re-checks permissions and
 * recalculates values on every request regardless of what is sent from here.
 */

import type { ApiErrorBody } from "./types";

const CSRF_COOKIE = "ztech_csrftoken";

/** An error the API answered with, carrying its machine-readable code. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.error?.message ?? fallback);
    this.name = "ApiError";
    this.status = status;
    this.code = body?.error?.code ?? "unknown_error";
    this.details = (body?.error?.details as Record<string, unknown>) ?? {};
  }

  /** The record was changed by someone else since it was loaded. */
  get isConflict(): boolean {
    return this.status === 409 || this.code === "stale_object";
  }

  get isAuthRequired(): boolean {
    return this.status === 401 || (this.status === 403 && this.code === "permission_denied" && !this.details);
  }

  get isPermissionDenied(): boolean {
    return this.status === 403;
  }

  /** Per-field messages, ready to show next to the inputs that produced them. */
  fieldErrors(): Record<string, string[]> {
    const result: Record<string, string[]> = {};
    for (const [field, value] of Object.entries(this.details)) {
      if (Array.isArray(value)) {
        result[field] = value.map(String);
      } else if (typeof value === "string") {
        result[field] = [value];
      }
    }
    return result;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let csrfPrimed = false;

/** Make sure the CSRF cookie exists before the first mutating request. */
async function ensureCsrfToken(): Promise<string | null> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  if (!csrfPrimed) {
    csrfPrimed = true;
    await fetch("/api/auth/csrf/", { credentials: "same-origin" });
  }
  return readCookie(CSRF_COOKIE);
}

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

interface RequestOptions {
  method?: Method;
  body?: unknown;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };

  if (method !== "GET") {
    const token = await ensureCsrfToken();
    if (token) headers["X-CSRFToken"] = token;
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(buildUrl(path, options.query), {
    method,
    headers,
    credentials: "same-origin",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, payload as ApiErrorBody | null, response.statusText);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal) =>
    request<T>(path, { method: "GET", query, signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
