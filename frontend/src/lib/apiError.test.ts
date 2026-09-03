// Non-locked coverage for apiError.ts (spec §7.3 / §6). The parseApiError oracle
// rows live in apiError.oracle.test.ts; these cover the helpers + hook.

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ValidationIssue } from "../types";
import {
  ApiError,
  fieldName,
  hasInlineFormError,
  isFieldError,
  parseApiError,
  useFormErrors,
} from "./apiError";

const issue = (loc: (string | number)[], msg = "bad"): ValidationIssue => ({
  loc,
  msg,
  type: "value_error",
});

describe("isFieldError", () => {
  it("is true for an array detail, false for a string detail", () => {
    expect(
      isFieldError(parseApiError(422, { detail: [issue(["body", "x"])] })),
    ).toBe(true);
    expect(isFieldError(parseApiError(409, { detail: "conflict" }))).toBe(
      false,
    );
  });
});

describe("fieldName", () => {
  it("returns the last loc segment, coerced to a string", () => {
    expect(fieldName(issue(["body", "username"]))).toBe("username");
    expect(fieldName(issue(["body", "ingredients", 3, "item"]))).toBe("item");
  });
});

describe("useFormErrors", () => {
  it("splits a ValidationIssue[] into field errors keyed by field path", () => {
    const err = parseApiError(422, {
      detail: [
        issue(["body", "title"], "required"),
        issue(["body", "servings"], "gt 0"),
      ],
    });
    const { result } = renderHook(() => useFormErrors(err));
    expect(result.current.fieldErrors).toEqual({
      title: "required",
      servings: "gt 0",
    });
    expect(result.current.formError).toBeNull();
  });

  it("keeps the nested row index in the key (spec §10.3)", () => {
    const err = parseApiError(422, {
      detail: [
        issue(["body", "ingredients", 0, "item"], "row 0"),
        issue(["body", "ingredients", 3, "item"], "row 3"),
      ],
    });
    const { result } = renderHook(() => useFormErrors(err));
    expect(result.current.fieldErrors).toEqual({
      "ingredients.0.item": "row 0",
      "ingredients.3.item": "row 3",
    });
  });

  it("collapses the Pydantic union branch tag the real backend emits (§6)", () => {
    // The running backend answers a bad object element with a `loc` that names
    // the winning union branch (`RecipeIngredientIn`) between the index and the
    // field, plus a sibling complaint against the losing `str` branch.
    const err = parseApiError(422, {
      detail: [
        issue(
          ["body", "ingredients", 1, "RecipeIngredientIn", "quantity"],
          "Input should be greater than 0",
        ),
        issue(
          ["body", "ingredients", 1, "str"],
          "Input should be a valid string",
        ),
        issue(
          ["body", "ingredients", 0, "RecipeIngredientIn", "qty"],
          "Extra inputs are not permitted",
        ),
      ],
    });
    const { result } = renderHook(() => useFormErrors(err));
    expect(result.current.fieldErrors).toEqual({
      "ingredients.1.quantity": "Input should be greater than 0",
      "ingredients.0.qty": "Extra inputs are not permitted",
    });
  });

  it("only collapses a segment that looks like a union branch tag", () => {
    // a hypothetical future `list[Object]` field — its own snake_case nested key
    // sits right after the index and must survive untouched.
    const err = parseApiError(422, {
      detail: [issue(["body", "lines", 2, "unit_price"], "required")],
    });
    const { result } = renderHook(() => useFormErrors(err));
    expect(result.current.fieldErrors).toEqual({
      "lines.2.unit_price": "required",
    });
  });

  it("keeps the first message when a key appears twice", () => {
    const err = parseApiError(422, {
      detail: [
        issue(["body", "title"], "first"),
        issue(["body", "title"], "second"),
      ],
    });
    const { result } = renderHook(() => useFormErrors(err));
    expect(result.current.fieldErrors).toEqual({ title: "first" });
  });

  it("surfaces a client-error string detail as a form-level error", () => {
    const err = parseApiError(422, {
      detail: "quantity and unit must be set together",
    });
    const { result } = renderHook(() => useFormErrors(err));
    expect(result.current).toEqual({
      fieldErrors: {},
      formError: "quantity and unit must be set together",
    });
  });

  it("does not surface a 5xx / 404 / transport string as a form error (§6)", () => {
    for (const status of [500, 404, 0]) {
      const err = parseApiError(status, { detail: "server said no" });
      const { result } = renderHook(() => useFormErrors(err));
      expect(result.current.formError).toBeNull();
    }
  });

  it("yields empties for a non-ApiError value", () => {
    const { result } = renderHook(() => useFormErrors(new Error("boom")));
    expect(result.current).toEqual({ fieldErrors: {}, formError: null });
  });

  it("yields empties for null", () => {
    const { result } = renderHook(() => useFormErrors(null));
    expect(result.current).toEqual({ fieldErrors: {}, formError: null });
  });

  it("returns a fresh object each call (no shared mutable singleton)", () => {
    const a = renderHook(() => useFormErrors(null)).result.current;
    const b = renderHook(() => useFormErrors(undefined)).result.current;
    expect(a).not.toBe(b);
    a.fieldErrors.x = "mutated";
    expect(b.fieldErrors).toEqual({});
  });

  it("memoizes the result while the error identity is stable", () => {
    const err = parseApiError(409, { detail: "conflict" });
    const { result, rerender } = renderHook(() => useFormErrors(err));
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });
});

describe("hasInlineFormError", () => {
  it("is true for a field error and a client-error string banner", () => {
    expect(
      hasInlineFormError(
        parseApiError(422, { detail: [issue(["body", "x"])] }),
      ),
    ).toBe(true);
    expect(
      hasInlineFormError(
        parseApiError(403, { detail: "registration disabled" }),
      ),
    ).toBe(true);
    expect(
      hasInlineFormError(parseApiError(409, { detail: "username taken" })),
    ).toBe(true);
  });

  it("is false when the failure belongs on a toast (§6)", () => {
    for (const status of [0, 404, 500, 503]) {
      expect(
        hasInlineFormError(parseApiError(status, { detail: "server said no" })),
      ).toBe(false);
    }
    expect(hasInlineFormError(new Error("boom"))).toBe(false);
    expect(hasInlineFormError(null)).toBe(false);
  });
});

describe("ApiError", () => {
  it("is an Error subclass carrying status + detail", () => {
    const e = new ApiError(404, "Not Found");
    expect(e).toBeInstanceOf(Error);
    expect(e.status).toBe(404);
    expect(e.message).toBe("Not Found");
  });
});
