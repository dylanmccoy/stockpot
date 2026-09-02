// Shared test utilities for exercising the HTTP client / error surfaces.

import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "../lib/apiError";

/** Await a promise that must reject, returning the thrown `ApiError`. */
export async function rejection(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected the request to reject");
}

/** A `QueryClient` with retries off — the default for component/flow tests so a
 *  failing request surfaces immediately. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}
