// Non-locked coverage for format.ts (spec §7.2). The formatQuantity oracle rows
// live in format.oracle.test.ts; these add formatDateTime plus extra cases.

import { describe, expect, it } from "vitest";
import { formatDateTime, formatQuantity } from "./format";

describe("formatQuantity — extra cases", () => {
  it("returns '' for a non-finite value", () => {
    expect(formatQuantity(NaN, "cup")).toBe("");
    expect(formatQuantity(Infinity, "g")).toBe("");
  });

  it("snaps counts to an integer for 'unit' and 'each' units too", () => {
    expect(formatQuantity(3.004, "unit")).toBe("3");
    expect(formatQuantity(0.999, "each")).toBe("1");
  });

  it("does not fraction-render a canonical bulk unit under 10", () => {
    expect(formatQuantity(0.5, "g")).toBe("0.5");
    expect(formatQuantity(2.5, "ml")).toBe("2.5");
  });

  it("rounds a non-bulk, non-snapping value to 3 significant figures", () => {
    expect(formatQuantity(266.1616, "cup")).toBe("266");
    expect(formatQuantity(0.19, "tsp")).toBe("0.19");
  });

  it("keeps an integer count exact even when far from any fraction", () => {
    expect(formatQuantity(5, null)).toBe("5");
  });
});

const DATETIME_SHAPE =
  /^[A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2}\s?(AM|PM)$/;

describe("formatDateTime", () => {
  it("renders the locale short form (spec §7.2 example shape)", () => {
    // Timezone-dependent wall-clock, so assert on shape + the stable fields.
    const out = formatDateTime("2026-08-28T18:12:00+00:00");
    expect(out).toMatch(DATETIME_SHAPE);
    expect(out).toContain("2026");
  });

  it("returns '' for an unparseable string", () => {
    expect(formatDateTime("not a date")).toBe("");
    expect(formatDateTime("")).toBe("");
  });
});
