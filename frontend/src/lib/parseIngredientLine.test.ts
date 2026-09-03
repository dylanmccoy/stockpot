import { describe, expect, it } from "vitest";
import { parseIngredientLine } from "./parseIngredientLine";

// Not a locked oracle (frontend spec §10.3 — the server is the source of
// truth). These cases pin the preview parse against the backend
// `parse_ingredient` behaviour it mirrors.

describe("parseIngredientLine", () => {
  it("splits quantity / unit / item", () => {
    expect(parseIngredientLine("2 tbsp olive oil")).toEqual({
      quantity: 2,
      unit: "tbsp",
      item: "olive oil",
      note: null,
    });
  });

  it("keeps a leading count with no unit as quantity + item", () => {
    expect(parseIngredientLine("1 onion, diced")).toEqual({
      quantity: 1,
      unit: null,
      item: "onion, diced",
      note: null,
    });
  });

  it("reads a simple fraction, a vulgar fraction, and a mixed number", () => {
    expect(parseIngredientLine("1/2 tsp cumin")).toMatchObject({
      quantity: 0.5,
      unit: "tsp",
      item: "cumin",
    });
    expect(parseIngredientLine("½ tsp salt")).toMatchObject({
      quantity: 0.5,
      unit: "tsp",
      item: "salt",
    });
    expect(parseIngredientLine("1 1/2 cups stock")).toMatchObject({
      quantity: 1.5,
      unit: "cups",
      item: "stock",
    });
  });

  it("pulls a unit off a no-space quantity like 1kg", () => {
    expect(parseIngredientLine("1kg potatoes")).toEqual({
      quantity: 1,
      unit: "kg",
      item: "potatoes",
      note: null,
    });
  });

  it("routes 'to taste' to the note and nulls the quantity", () => {
    expect(parseIngredientLine("salt to taste")).toEqual({
      quantity: null,
      unit: null,
      item: "salt",
      note: "to taste",
    });
    expect(parseIngredientLine("1 tsp black pepper, to taste")).toMatchObject({
      quantity: null,
      note: "to taste",
    });
  });

  it("extracts a parenthetical as the note", () => {
    // unit is stored as it appeared (lower-cased), not singularised.
    expect(parseIngredientLine("2 cloves garlic (minced)")).toEqual({
      quantity: 2,
      unit: "cloves",
      item: "garlic",
      note: "minced",
    });
  });

  it("leaves an unparseable line entirely as the item", () => {
    expect(parseIngredientLine("zest of 1 lemon")).toEqual({
      quantity: null,
      unit: null,
      item: "zest of 1 lemon",
      note: null,
    });
  });

  it("never returns an empty item", () => {
    expect(parseIngredientLine("   ").item).toBe("ingredient");
  });

  it("folds Unicode decimal digits to ASCII like Python's \\d + float", () => {
    expect(parseIngredientLine("１２ cup rice")).toEqual({
      quantity: 12,
      unit: "cup",
      item: "rice",
      note: null,
    });
  });

  it("strips every 'to taste', not just the first", () => {
    expect(
      parseIngredientLine("1 tsp salt to taste, or more to taste"),
    ).toMatchObject({ quantity: null, note: "to taste" });
    expect(
      parseIngredientLine("1 tsp salt to taste, or more to taste").item,
    ).not.toMatch(/to\s+taste/i);
  });
});
