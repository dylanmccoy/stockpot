// Non-locked coverage for parseIngredients (spec §7.1). The oracle rows live in
// parseIngredients.oracle.test.ts; these are additional black-box cases.

import { describe, expect, it } from "vitest";
import { parseIngredients } from "./parseIngredients";

describe("parseIngredients — extra cases", () => {
  it("strips a marker before header detection ('- Sauce:' is still a header)", () => {
    expect(parseIngredients("- Sauce:\n1 tbsp miso")).toEqual(["1 tbsp miso"]);
  });

  it("treats a CRLF block the same as LF (trim removes the stray \\r)", () => {
    expect(parseIngredients("2 eggs\r\n1 cup flour")).toEqual([
      "2 eggs",
      "1 cup flour",
    ]);
  });

  it("does not rejoin a soft-wrapped line (v1 scope)", () => {
    expect(
      parseIngredients("2 tbsp olive oil, plus more\nfor drizzling"),
    ).toEqual(["2 tbsp olive oil, plus more", "for drizzling"]);
  });

  it("keeps a bare no-quantity ingredient that is not a header", () => {
    expect(parseIngredients("salt\nfreshly ground pepper")).toEqual([
      "salt",
      "freshly ground pepper",
    ]);
  });

  it("keeps a colon line that leads with a unicode fraction", () => {
    expect(parseIngredients("½ lemon: juiced and zested")).toEqual([
      "½ lemon: juiced and zested",
    ]);
  });

  it("drops a header that leads with a non-quantity word ending in ':'", () => {
    expect(parseIngredients("Dry ingredients:\n300 g flour")).toEqual([
      "300 g flour",
    ]);
  });

  it("returns [] for whitespace-only input", () => {
    expect(parseIngredients("  \n\t\n \n")).toEqual([]);
  });
});
