import { Badge } from "./Badge";
import type { BadgeTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { Column } from "./DataTable";
import { formatQuantity } from "../lib/format";
import type { CookDeductionRead, CookDeductionReason } from "../types";

// The expanded body of a `CookLogRow` (spec §10.8): one table row per
// `CookDeductionRead`, each carrying a plain-language chip for its `reason`.
// Rendered only for a cook that deducted stock — a `deduct: false` log has no
// detail table at all.

interface ChipMeta {
  label: string;
  tone: BadgeTone;
  /** Non-colour glyph — status is never colour-only (spec §9). */
  icon: string;
}

/** All five `CookDeductionReason` values get a chip. `ok` is deliberately quiet
 *  (neutral tone) rather than absent, so every row reads as explained. */
const CHIP: Record<CookDeductionReason, ChipMeta> = {
  ok: { label: "deducted", tone: "neutral", icon: "✓" },
  "clamped to 0": { label: "ran out", tone: "warn", icon: "△" },
  "not in inventory": { label: "not tracked", tone: "neutral", icon: "•" },
  "have uncertain (incompatible unit)": {
    label: "check what you have",
    tone: "warn",
    icon: "?",
  },
  "to taste": { label: "to taste", tone: "neutral", icon: "•" },
};

/** Server order is already the display order; the index is a stable row key
 *  since `item` can repeat across groups. */
type Row = CookDeductionRead & { key: number };

/** `a → b` with the unit word appended once; a `null` side shows as `—`. */
function rangeLabel(
  a: number | null,
  b: number | null,
  unit: string | null,
): string {
  const left = formatQuantity(a, unit) || "—";
  const right = formatQuantity(b, unit) || "—";
  const tail = unit ? ` ${unit}` : "";
  return `${left} → ${right}${tail}`;
}

const columns: Column<Row>[] = [
  { key: "item", header: "Ingredient", render: (d) => d.item },
  {
    key: "amount",
    header: "Requested → deducted",
    align: "end",
    render: (d) => rangeLabel(d.requested, d.deducted, d.inventory_unit),
  },
  {
    key: "stock",
    header: "Before → after",
    align: "end",
    render: (d) => rangeLabel(d.before, d.after, d.inventory_unit),
  },
  {
    key: "reason",
    header: "Note",
    render: (d) => {
      const chip = CHIP[d.reason];
      return (
        <Badge tone={chip.tone} icon={chip.icon}>
          {chip.label}
        </Badge>
      );
    },
  },
];

export function DeductionDetail({
  deductions,
}: {
  deductions: CookDeductionRead[];
}) {
  const rows: Row[] = deductions.map((d, key) => ({ ...d, key }));
  return (
    <DataTable
      caption="Per-ingredient stock change for this cook"
      columns={columns}
      rows={rows}
      rowKey={(d) => d.key}
      empty="No ingredients were deducted."
    />
  );
}
