// LOCKED oracle suite — spec §7.2 (R-8), plan "Contract-test gate".
//
// Every row below is a verbatim transcription of the spec §7.2 table and is
// ACCEPTED. The implementation pass may add cases but must not edit or delete
// an accepted expected value here. A wrong oracle is fixed by editing spec.md
// and this file together, with the reason recorded in docs/frontend/decisions.md.

import { describe, expect, it } from "vitest";
import { formatQuantity } from "./format";

interface Row {
  id: string;
  value: number | null;
  unit: string | null;
  output: string;
}

const rows: Row[] = [
  { id: "F1", value: 0.5, unit: "cup", output: "½" },
  { id: "F2", value: 1.5, unit: "cups", output: "1½" },
  { id: "F3", value: 0.3333333, unit: "cup", output: "⅓" },
  // 0.26 is 4% off ¼ = 0.25, outside the 2% snap band → decimal
  { id: "F4", value: 0.26, unit: "tsp", output: "0.26" },
  { id: "F5", value: 2, unit: null, output: "2" },
  { id: "F6", value: 2.997, unit: null, output: "3" },
  { id: "F7", value: 473.176, unit: "ml", output: "473" },
  { id: "F8", value: 266.1616, unit: "ml", output: "266" },
  { id: "F9", value: 0.0264554, unit: "g", output: "0.0265" },
  { id: "F10", value: 12000, unit: "g", output: "12000" },
  { id: "F11", value: 1.25, unit: "lb", output: "1¼" },
  { id: "F12", value: 0.125, unit: "tsp", output: "⅛" },
  { id: "F13", value: 7.5, unit: "cup", output: "7½" },
  // value >= 10 → no fraction
  { id: "F14", value: 10.5, unit: "cup", output: "10.5" },
  { id: "F15", value: null, unit: "g", output: "" },
];

describe("formatQuantity — locked oracle (spec §7.2)", () => {
  it.each(rows)("$id  ($value, $unit) → $output", ({ value, unit, output }) => {
    expect(formatQuantity(value, unit)).toBe(output);
  });
});
