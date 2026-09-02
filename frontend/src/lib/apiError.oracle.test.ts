// LOCKED oracle suite — spec §7.3, plan "Contract-test gate".
//
// Every row below is a verbatim transcription of the spec §7.3 table and is
// ACCEPTED. The implementation pass may add cases but must not edit or delete
// an accepted expected value here. A wrong oracle is fixed by editing spec.md
// and this file together, with the reason recorded in docs/frontend/decisions.md.

import { describe, expect, it } from "vitest";
import type { ValidationIssue } from "../types";
import { ApiError, fieldName, parseApiError } from "./apiError";

describe("parseApiError — locked oracle (spec §7.3)", () => {
  it("E1  422 + ValidationIssue[] → the array, length 1, loc tail 'username'", () => {
    const body = {
      detail: [
        {
          loc: ["body", "username"],
          msg: "field required",
          type: "value_error.missing",
        },
      ],
    };
    const e = parseApiError(422, body);
    expect(e).toBeInstanceOf(ApiError);
    expect(e.status).toBe(422);
    expect(Array.isArray(e.detail)).toBe(true);
    const detail = e.detail as ValidationIssue[];
    expect(detail).toHaveLength(1);
    expect(fieldName(detail[0])).toBe("username");
  });

  it("E2  401 + string detail → verbatim", () => {
    const e = parseApiError(401, { detail: "not authenticated" });
    expect(e.status).toBe(401);
    expect(e.detail).toBe("not authenticated");
  });

  it("E3  409 + string detail → verbatim", () => {
    const e = parseApiError(409, { detail: "conflict" });
    expect(e.detail).toBe("conflict");
  });

  it("E4  500 + non-object body → standard reason phrase", () => {
    const e = parseApiError(500, "<html>502 Bad Gateway</html>");
    expect(e.status).toBe(500);
    expect(e.detail).toBe("Internal Server Error");
  });

  it("E5  404 + object without detail → standard reason phrase", () => {
    const e = parseApiError(404, {});
    expect(e.detail).toBe("Not Found");
  });

  it("E6  400 + null body → 'Request failed' (no phrase for 400)", () => {
    const e = parseApiError(400, null);
    expect(e.status).toBe(400);
    expect(e.detail).toBe("Request failed");
  });

  it("E7  422 + string detail → string, not array", () => {
    const e = parseApiError(422, {
      detail: "quantity and unit must be set together",
    });
    expect(Array.isArray(e.detail)).toBe(false);
    expect(e.detail).toBe("quantity and unit must be set together");
  });

  it("E8  403 + ValidationIssue[] → the array, length 2", () => {
    const body = {
      detail: [
        { loc: ["body", "code"], msg: "x", type: "y" },
        { loc: ["body", "username"], msg: "z", type: "w" },
      ],
    };
    const e = parseApiError(403, body);
    expect(e.status).toBe(403);
    expect(Array.isArray(e.detail)).toBe(true);
    expect(e.detail as ValidationIssue[]).toHaveLength(2);
  });
});
