// Quantity / number / datetime formatting — spec §7.2 (R-8). Responses carry
// raw floats; nothing else in the app rounds or renders a number for display.
// Locked oracle: format.oracle.test.ts.

const COMMON_FRACTIONS: ReadonlyArray<readonly [number, string]> = [
  [1 / 8, "⅛"],
  [1 / 4, "¼"],
  [1 / 3, "⅓"],
  [1 / 2, "½"],
  [2 / 3, "⅔"],
  [3 / 4, "¾"],
];

const FRACTION_TOLERANCE = 0.02; // relative, per spec §7.2
const COUNT_TOLERANCE = 0.01; // absolute, per spec §7.2

function toThreeSigFigs(value: number): string {
  if (value === 0) return "0";
  // toPrecision may yield exponential notation; Number(...) back to a plain
  // decimal and drop trailing zeros. No thousands separators in v1.
  return String(Number(value.toPrecision(3)));
}

function snapToFraction(value: number): string | null {
  const whole = Math.floor(value);
  const frac = value - whole;
  for (const [target, glyph] of COMMON_FRACTIONS) {
    if (Math.abs(frac - target) <= FRACTION_TOLERANCE * target) {
      return whole === 0 ? glyph : `${whole}${glyph}`;
    }
  }
  return null;
}

export function formatQuantity(
  value: number | null,
  unit: string | null,
): string {
  if (value === null || !Number.isFinite(value)) return "";

  const isBulk = unit === "g" || unit === "ml";
  const isCount = unit === null || unit === "unit" || unit === "each";

  if (!isBulk && value > 0 && value < 10) {
    const snapped = snapToFraction(value);
    if (snapped !== null) return snapped;
  }

  if (isCount && Math.abs(value - Math.round(value)) <= COUNT_TOLERANCE) {
    return String(Math.round(value));
  }

  return toThreeSigFigs(value);
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
