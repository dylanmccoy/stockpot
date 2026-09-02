import { describe, expect, it } from "vitest";
import type { HttpHandler } from "msw";
import { server } from "./server";
import { errorHandlers } from "./errorHandlers";
import { request } from "../api/client";
import { ApiError, fieldName } from "../lib/apiError";
import { rejection } from "./helpers";
import type { ValidationIssue } from "../types";

// Proves every docs/frontend/spec.md §6 catalog row has a working handler and
// that api/client.ts normalizes each into the expected ApiError. The per-row
// *FE surface* assertions (toast / inline / redirect) come in Phase 7.

interface Row {
  name: string;
  handler: HttpHandler;
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  status: number;
  detail: string | "ARRAY";
}

const rows: Row[] = [
  {
    name: "422 ValidationIssue[]",
    handler: errorHandlers.validation("post", "/api/recipes", "title"),
    method: "POST",
    path: "/recipes",
    status: 422,
    detail: "ARRAY",
  },
  {
    name: "422 domain-rule string",
    handler: errorHandlers.domainRule(
      "patch",
      "/api/inventory/:id",
      "unit is required when setting quantity",
    ),
    method: "PATCH",
    path: "/inventory/1",
    status: 422,
    detail: "unit is required when setting quantity",
  },
  {
    name: "401 not authenticated",
    handler: errorHandlers.notAuthenticated("get", "/api/recipes"),
    method: "GET",
    path: "/recipes",
    status: 401,
    detail: "not authenticated",
  },
  {
    name: "401 invalid login",
    handler: errorHandlers.invalidLogin(),
    method: "POST",
    path: "/auth/login",
    status: 401,
    detail: "invalid username or password",
  },
  {
    name: "403 registration disabled",
    handler: errorHandlers.registrationDisabled(),
    method: "POST",
    path: "/auth/register",
    status: 403,
    detail: "registration disabled",
  },
  {
    name: "403 invalid registration code",
    handler: errorHandlers.invalidRegistrationCode(),
    method: "POST",
    path: "/auth/register",
    status: 403,
    detail: "invalid registration code",
  },
  {
    name: "404 resource not found",
    handler: errorHandlers.notFound("get", "/api/recipes/:id", "recipe"),
    method: "GET",
    path: "/recipes/999",
    status: 404,
    detail: "recipe not found",
  },
  {
    name: "409 conflict (integrity / lock)",
    handler: errorHandlers.conflict("post", "/api/recipes/:id/cook"),
    method: "POST",
    path: "/recipes/1/cook",
    status: 409,
    detail: "conflict",
  },
  {
    name: "409 username taken",
    handler: errorHandlers.usernameTaken(),
    method: "POST",
    path: "/auth/register",
    status: 409,
    detail: "username taken",
  },
  {
    name: "409 match_name in use",
    handler: errorHandlers.matchNameInUse(),
    method: "PATCH",
    path: "/inventory/1",
    status: 409,
    detail: "match_name already in use for this bucket",
  },
  {
    name: "409 list is not active",
    handler: errorHandlers.listNotActive("post", "/api/grocery/:id/archive"),
    method: "POST",
    path: "/grocery/1/archive",
    status: 409,
    detail: "list is not active",
  },
  {
    name: "409 frozen grocery line",
    handler: errorHandlers.frozenLine(
      "delete",
      "/api/grocery/:id/items/:itemId",
    ),
    method: "DELETE",
    path: "/grocery/1/items/2",
    status: 409,
    detail: "conflict",
  },
  {
    name: "500 server error",
    handler: errorHandlers.serverError("get", "/api/cook-logs"),
    method: "GET",
    path: "/cook-logs",
    status: 500,
    detail: "Internal Server Error",
  },
];

describe("§6 error catalog handlers", () => {
  it.each(rows)("$name → ApiError { status: $status }", async (row) => {
    server.use(row.handler);
    const err = await rejection(request(row.path, { method: row.method }));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(row.status);
    if (row.detail === "ARRAY") {
      const detail = err.detail as ValidationIssue[];
      expect(Array.isArray(detail)).toBe(true);
      expect(fieldName(detail[0])).toBe("title");
    } else {
      expect(err.detail).toBe(row.detail);
    }
  });
});
