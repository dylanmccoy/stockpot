// Shared test utilities for exercising the HTTP client / error surfaces.

import { ApiError } from "../api/client";
import type { ValidationIssue } from "../types";

/** Await a promise that must reject, returning the thrown `ApiError`. */
export async function rejection(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected the request to reject");
}

/** The last `loc` segment of a validation issue (Phase 1's `fieldName` helper). */
export const lastLoc = (issue: ValidationIssue): string | number =>
  issue.loc[issue.loc.length - 1];
