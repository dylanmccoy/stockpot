// API error normalization — spec §7.3 / §6. FastAPI returns `{ detail: string }`
// or `{ detail: ValidationIssue[] }`; everything else is a degenerate case.
// `api/client.ts` throws the `ApiError` produced here. Locked oracle:
// apiError.oracle.test.ts.

import { useMemo } from "react";
import type { ValidationIssue } from "../types";

// Standard reason phrases we surface when the body carries no usable `detail`.
// Deliberately sparse: anything not listed falls back to "Request failed"
// (spec §7.3 oracle rows E4–E6).
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

/** Normalize a status + parsed response body into an `ApiError`. `204` never
 *  reaches here. */
export function parseApiError(status: number, body: unknown): ApiError {
  if (body !== null && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return new ApiError(status, detail);
    if (Array.isArray(detail)) {
      return new ApiError(status, detail as ValidationIssue[]);
    }
  }
  return new ApiError(status, REASON_PHRASE[status] ?? "Request failed");
}

export function isFieldError(
  e: ApiError,
): e is ApiError & { detail: ValidationIssue[] } {
  return Array.isArray(e.detail);
}

/** The form field an issue targets: the last segment of its `loc` (spec §6). */
export function fieldName(issue: ValidationIssue): string {
  return String(issue.loc[issue.loc.length - 1]);
}

/** How Pydantic v2 names the branch of an *untagged* union in an error `loc`:
 *  a model branch gets its class name (`RecipeIngredientIn` — every schema in
 *  this API is PascalCase), a builtin branch its type name. This is the closed
 *  set of builtin scalar tags — not a guess at future needs. */
const UNION_SCALAR_TAGS = new Set(["str", "int", "float", "bool"]);
const isUnionBranchTag = (seg: string): boolean =>
  UNION_SCALAR_TAGS.has(seg) || /^[A-Z][A-Za-z0-9]*$/.test(seg);

/** True when this issue is untagged-union *losing*-branch noise: its `loc` ends
 *  in a branch tag, e.g. `["body","ingredients",3,"str"]` — the "Input should be
 *  a valid string" complaint against an object element. It names no field, so it
 *  is dropped before mapping (spec §6, §7.3). */
export function isUnionBranchNoise(issue: ValidationIssue): boolean {
  const last = issue.loc[issue.loc.length - 1];
  return typeof last === "string" && isUnionBranchTag(last);
}

/** Collapse the *interior* branch-tag segment Pydantic inserts for an
 *  untagged-union member error. The real backend answers a bad object element
 *  with `["body","ingredients",3,"RecipeIngredientIn","item"]`, not the
 *  `["body","ingredients",3,"item"]` spec §10.3 assumes. A tag only appears
 *  directly after a numeric index and before the real field; matching on
 *  `isUnionBranchTag` (not just "any string after a number") keeps a future
 *  `list[Object]` field whose own nested key is snake_case from being
 *  mis-collapsed. A *trailing* tag (element neither branch validated — no field
 *  named) is left for `isUnionBranchNoise` to drop. */
function normalizeLoc(loc: (string | number)[]): (string | number)[] {
  const out: (string | number)[] = [];
  loc.forEach((seg, i) => {
    const interiorTag =
      typeof seg === "string" &&
      typeof out[out.length - 1] === "number" &&
      i < loc.length - 1 &&
      isUnionBranchTag(seg);
    if (!interiorTag) out.push(seg);
  });
  return out;
}

/** The full field path an issue targets, `body`-prefix dropped and joined with
 *  `.` — so a flat field stays `"servings"` while a nested one becomes
 *  `"ingredients.3.item"` (spec §10.3 maps `["body","ingredients",3,"item"]` to
 *  a row + field). Pydantic union branch tags are collapsed first
 *  (`normalizeLoc`). */
function fieldPath(issue: ValidationIssue): string {
  const loc = normalizeLoc(issue.loc);
  const segs = loc[0] === "body" ? loc.slice(1) : loc;
  return segs.length > 0 ? segs.join(".") : fieldName(issue);
}

// String `detail` renders inline on the form only for client-error statuses;
// `404` is a not-found panel and `5xx` / transport (`status 0`) are toasts (§6).
function isFormLevelStatus(status: number): boolean {
  return status >= 400 && status < 500 && status !== 404;
}

export interface FormErrors {
  /** Field-level messages, keyed by `fieldPath`; first message per key wins. */
  fieldErrors: Record<string, string>;
  /** A form-level banner message, or `null`. */
  formError: string | null;
}

/** Copy for a failure with no inline surface — spec §6 routes transport / `5xx`
 *  / unexpected errors to a generic toast. */
export const GENERIC_ERROR_MESSAGE = "Something went wrong. Try again.";

/** Whether a thrown value has a place on a form's own inline surface — a field
 *  error or the form-level banner. When `false` the failure belongs on a toast:
 *  a transport failure, a `5xx`, a `404`, or a non-`ApiError` (spec §6). */
export function hasInlineFormError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  if (isFieldError(error)) return true;
  return typeof error.detail === "string" && isFormLevelStatus(error.status);
}

function splitFormErrors(error: unknown): FormErrors {
  if (!(error instanceof ApiError)) return { fieldErrors: {}, formError: null };
  if (isFieldError(error)) {
    const fieldErrors: Record<string, string> = {};
    for (const issue of error.detail) {
      if (isUnionBranchNoise(issue)) continue;
      const key = fieldPath(issue);
      if (!(key in fieldErrors)) fieldErrors[key] = issue.msg;
    }
    return { fieldErrors, formError: null };
  }
  const formError =
    typeof error.detail === "string" && isFormLevelStatus(error.status)
      ? error.detail
      : null;
  return { fieldErrors: {}, formError };
}

/** Splits an `ApiError` into field-level (`ValidationIssue[]`) and form-level
 *  (string `detail`) parts for a form. Non-`ApiError` values, `5xx`, transport
 *  failures and `404`s yield empties — those surfaces (toast, not-found panel,
 *  `401` redirect) are owned elsewhere (§6). */
export function useFormErrors(error: unknown): FormErrors {
  return useMemo(() => splitFormErrors(error), [error]);
}
