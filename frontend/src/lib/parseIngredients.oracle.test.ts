// LOCKED oracle suite — spec §7.1 (D2 / R-9), plan "Contract-test gate".
//
// Every row below is a verbatim transcription of the spec §7.1 table and is
// ACCEPTED. The implementation pass may add cases but must not edit or delete
// an accepted expected value here. A wrong oracle is fixed by editing spec.md
// and this file together, with the reason recorded in docs/frontend/decisions.md.

import { describe, expect, it } from "vitest";
import { parseIngredients } from "./parseIngredients";

interface Row {
  id: string;
  input: string;
  output: string[];
}

const rows: Row[] = [
  {
    id: "P1",
    input: "2 tbsp olive oil\n1 onion, diced\n\nsalt to taste",
    output: ["2 tbsp olive oil", "1 onion, diced", "salt to taste"],
  },
  {
    id: "P2",
    input: "- 2 eggs\n* 1 cup flour\n• 1 tsp salt",
    output: ["2 eggs", "1 cup flour", "1 tsp salt"],
  },
  {
    id: "P3",
    input: "1. Preheat\n2) Mix",
    output: ["Preheat", "Mix"],
  },
  {
    id: "P4",
    input: "For the sauce:\n2 tbsp soy sauce\nFor the garnish:\n1 scallion",
    output: ["2 tbsp soy sauce", "1 scallion"],
  },
  {
    id: "P5",
    input: "   \n\t\n  2 cups rice  \n",
    output: ["2 cups rice"],
  },
  {
    id: "P6",
    input: "1/2 tsp cumin\n½ tsp salt\n1 1/2 cups stock",
    output: ["1/2 tsp cumin", "½ tsp salt", "1 1/2 cups stock"],
  },
  {
    id: "P7",
    // has a leading quantity → not a header even though it contains ":"
    input: "2 cups whole milk: room temp",
    output: ["2 cups whole milk: room temp"],
  },
  {
    id: "P8",
    input: "",
    output: [],
  },
  {
    id: "P9",
    input: "Chicken:\n  \n- Chicken thighs\n1kg potatoes",
    output: ["Chicken thighs", "1kg potatoes"],
  },
  {
    id: "P10",
    input: "3 large eggs\nzest of 1 lemon",
    output: ["3 large eggs", "zest of 1 lemon"],
  },
];

describe("parseIngredients — locked oracle (spec §7.1)", () => {
  it.each(rows)("$id", ({ input, output }) => {
    expect(parseIngredients(input)).toEqual(output);
  });
});
