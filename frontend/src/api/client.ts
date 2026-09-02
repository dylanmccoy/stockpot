// The one fetch wrapper. Every network call in the app goes through here.
//
//  - prefixes `/api` (calls pass the path without it, e.g. `/recipes`)
//  - injects `Authorization: Bearer <token>` from localStorage on every call
//    except `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/health`
//  - sends/receives JSON; sets `Content-Type` only when there is a body
//  - returns `undefined` for `204`
//  - normalizes both FastAPI error shapes into an `ApiError` and throws it
//  - a `401` on a gated route fires the registered unauthorized handler
//
// Phase 1 adds `lib/apiError.ts` with the locked `parseApiError` oracle suite.
// `lib/` is a pure leaf layer that `api/client.ts` may import (docs/frontend/
// spec.md §1 import direction), so the normalization below moves there then.

import type { ValidationIssue } from "../types";

const TOKEN_KEY = "recipe.token";

const PUBLIC_ROUTES = new Set([
  "POST /api/auth/login",
  "POST /api/auth/register",
  "GET /api/health",
]);

// Standard reason phrases we surface when the body carries no usable `detail`.
// Deliberately sparse: anything not listed falls back to "Request failed"
// (see docs/frontend/spec.md §7.3 oracle rows E4–E6).
const REASON_PHRASE: Record<number, string> = {
  404: "Not Found",
  500: "Internal Server Error",
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | ValidationIssue[];

  constructor(status: number, detail: string | ValidationIssue[]) {
    super(typeof detail === "string" ? detail : `${status} validation error`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Normalize a non-2xx response body into an `ApiError`. */
function toApiError(status: number, body: unknown): ApiError {
  if (body !== null && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return new ApiError(status, detail);
    if (Array.isArray(detail)) {
      return new ApiError(status, detail as ValidationIssue[]);
    }
  }
  return new ApiError(status, REASON_PHRASE[status] ?? "Request failed");
}

// ── token storage ──────────────────────────────────────────────────────────

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token === null) localStorage.removeItem(TOKEN_KEY);
    else localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable — nothing we can do */
  }
}

// ── unauthorized handler seam ──────────────────────────────────────────────
// `AuthProvider` registers a callback here so a `401` can clear the token, drop
// the query cache, and redirect to /login without the client importing React.

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(fn: UnauthorizedHandler | null): void {
  unauthorizedHandler = fn;
}

// ── request ────────────────────────────────────────────────────────────────

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

export async function request<T>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const method = opts.method ?? "GET";
  const url = path.startsWith("/api") ? path : `/api${path}`;
  const isPublic = PUBLIC_ROUTES.has(`${method} ${url}`);

  const headers: Record<string, string> = {};

  const token = getToken();
  if (token !== null && !isPublic) {
    headers.Authorization = `Bearer ${token}`;
  }

  let payload: BodyInit | undefined;
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: payload,
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "Network request failed");
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let parsed: unknown = null;
  if (text.length > 0) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    const error = toApiError(res.status, parsed);
    if (res.status === 401 && !isPublic) {
      unauthorizedHandler?.();
    }
    throw error;
  }

  return parsed as T;
}

export const client = {
  get: <T>(path: string, signal?: AbortSignal) =>
    request<T>(path, { method: "GET", signal }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
