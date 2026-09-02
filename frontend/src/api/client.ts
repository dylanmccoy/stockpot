// The one fetch wrapper. Every network call in the app goes through here.
//
//  - prefixes `/api` (calls pass the path without it, e.g. `/recipes`)
//  - injects `Authorization: Bearer <token>` from localStorage on every call
//    except `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/health`
//  - sends/receives JSON; sets `Content-Type` only when there is a body
//  - returns `undefined` for `204`
//  - normalizes both FastAPI error shapes into an `ApiError` and throws it
//    (via `lib/apiError.ts` — the locked `parseApiError` oracle, spec §7.3)
//  - a `401` on a gated route fires the registered unauthorized handler

import { ApiError, parseApiError } from "../lib/apiError";

const TOKEN_KEY = "recipe.token";

const PUBLIC_ROUTES = new Set([
  "POST /api/auth/login",
  "POST /api/auth/register",
  "GET /api/health",
]);

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
    const error = parseApiError(res.status, parsed);
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
