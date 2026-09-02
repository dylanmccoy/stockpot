// Shared test utilities for exercising the HTTP client / error surfaces.

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
