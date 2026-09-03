// One MSW error handler per docs/frontend/spec.md §6 catalog row. Tests opt into
// a row with `server.use(errorHandlers.<row>(...))` and assert the resulting FE
// surface (toast / inline-field / inline-form / redirect). Phase 7 exercises
// every row; Phase 0 only requires that the catalog is covered here.

import { http, HttpResponse, type HttpHandler } from "msw";
import type { ValidationIssue } from "../types";

type Method = "get" | "post" | "put" | "patch" | "delete";

const json = (status: number, detail: string | ValidationIssue[]) =>
  HttpResponse.json({ detail }, { status });

const issue = (field: string): ValidationIssue => ({
  loc: ["body", field],
  msg: "field required",
  type: "missing",
});

export const errorHandlers = {
  /** 422 · ValidationIssue[] — Pydantic field validation → inline per-field. */
  validation: (method: Method, path: string, field = "value"): HttpHandler =>
    http[method](path, () => json(422, [issue(field)])),

  /** 422 · ValidationIssue[] for a bad **object** ingredient element, in the
   *  exact union-tagged shape the running backend emits (frontend ticket 15):
   *  the field error names the winning `RecipeIngredientIn` branch, and a
   *  sibling complains against the losing `str` branch. `lib/apiError.ts`
   *  collapses the tag to `ingredients.<idx>.<field>` and drops the sibling. */
  ingredientMemberValidation: (
    idx: number,
    field = "item",
    msg = "field required",
  ): HttpHandler =>
    http.post("/api/recipes", () =>
      json(422, [
        {
          loc: ["body", "ingredients", idx, "RecipeIngredientIn", field],
          msg,
          type: "missing",
        },
        {
          loc: ["body", "ingredients", idx, "str"],
          msg: "Input should be a valid string",
          type: "string_type",
        },
      ]),
    ),

  /** 422 · string — a named domain rule → inline form-level banner (verbatim). */
  domainRule: (method: Method, path: string, message: string): HttpHandler =>
    http[method](path, () => json(422, message)),

  /** 401 · "not authenticated" — bad/missing/expired token → silent redirect. */
  notAuthenticated: (method: Method, path: string): HttpHandler =>
    http[method](path, () => json(401, "not authenticated")),

  /** 401 · "invalid username or password" — login failure → inline form-level. */
  invalidLogin: (): HttpHandler =>
    http.post("/api/auth/login", () =>
      json(401, "invalid username or password"),
    ),

  /** 403 · registration refused → inline form-level (verbatim). */
  registrationDisabled: (): HttpHandler =>
    http.post("/api/auth/register", () => json(403, "registration disabled")),

  invalidRegistrationCode: (): HttpHandler =>
    http.post("/api/auth/register", () =>
      json(403, "invalid registration code"),
    ),

  /** 404 · "<resource> not found" → in-content not-found panel. */
  notFound: (method: Method, path: string, resource = "recipe"): HttpHandler =>
    http[method](path, () => json(404, `${resource} not found`)),

  /** 409 · "conflict" — IntegrityError or lock timeout → toast + refetch. */
  conflict: (method: Method, path: string): HttpHandler =>
    http[method](path, () => json(409, "conflict")),

  /** 409 · "username taken" → inline field (username). */
  usernameTaken: (): HttpHandler =>
    http.post("/api/auth/register", () => json(409, "username taken")),

  /** 409 · match_name collision on PATCH → inline field (match_name). */
  matchNameInUse: (path = "/api/inventory/:id"): HttpHandler =>
    http.patch(path, () =>
      json(409, "match_name already in use for this bucket"),
    ),

  /** 409 · "list is not active" — mutating an archived list → toast + refetch. */
  listNotActive: (method: Method, path: string): HttpHandler =>
    http[method](path, () => json(409, "list is not active")),

  /** 409 · "conflict" on a frozen grocery line → toast + refetch. */
  frozenLine: (method: Method, path: string): HttpHandler =>
    http[method](path, () => json(409, "conflict")),

  /** 500 · generic server error → generic toast. */
  serverError: (method: Method, path: string): HttpHandler =>
    http[method](path, () => json(500, "Internal Server Error")),
};
