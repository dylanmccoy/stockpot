// Production `QueryClient` defaults (spec §11 O-5: React Query defaults +
// a visible "reconnecting" hint for the store-walk case — grocery detail on a
// phone with flaky wifi — no service worker / offline cache in v1).
//
// Test code does NOT use this — screen/flow tests build their own minimal
// client via `test/helpers.ts`' `makeQueryClient()` (retries off, so a failing
// request surfaces immediately instead of stalling a test on a backoff timer).

import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "../lib/apiError";

// `api/client.ts` marks a transport-level failure (fetch threw before a
// response arrived — offline, DNS blip, request timeout) with `status: 0`.
// That is the only case worth retrying: a real API error (4xx/5xx) is an
// answer from the server and will not change on retry, so retrying it just
// delays the toast/inline surface the user is waiting on (spec §6).
const isNetworkFailure = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 0;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) =>
          isNetworkFailure(error) && failureCount < 5,
        retryDelay: (failureCount) =>
          Math.min(1000 * 2 ** failureCount, 30_000),
        // Explicitly 0, not left to default: on the store walk, stock/list
        // state can change from another device between screens, and nothing
        // here polls in the background — a query only refetches on mount,
        // reconnect, or an explicit invalidate — so staying "stale" buys no
        // fewer requests, only a chance of showing a walker last screen's
        // numbers on this one.
        staleTime: 0,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
      },
      mutations: {
        // Never auto-retry a write blind — a re-sent cook/submit/POST could
        // double-apply. The mutation's own `onError` toast (spec §6) is the
        // recovery path; the user decides whether to retry.
        retry: false,
      },
    },
  });
}
