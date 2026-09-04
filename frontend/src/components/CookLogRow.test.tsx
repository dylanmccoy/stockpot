import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CookLogRow, deductionSummary } from "./CookLogRow";
import { makeCookLog, makeDeduction as ded } from "../test/handlers";
import { formatDateTime } from "../lib/format";
import type { CookLogRead } from "../types";

const AT = "2026-09-01T12:00:00+00:00";

/** A deducted cook by "sam" at `AT` — the shape most row tests want. */
function log(overrides: Partial<CookLogRead> = {}): CookLogRead {
  return makeCookLog({
    id: 7,
    multiplier: 2,
    deducted: true,
    cooked_at: AT,
    cooked_by: { id: 1, username: "sam" },
    deductions: [ded("ok", "flour")],
    ...overrides,
  });
}

function renderRow(l: CookLogRead, showRecipeTitle = false) {
  return render(
    <ul>
      <CookLogRow log={l} showRecipeTitle={showRecipeTitle} />
    </ul>,
  );
}

describe("CookLogRow — collapsed line", () => {
  it("shows the date, who cooked it, and the multiplier", () => {
    renderRow(log({ multiplier: 1.5 }));
    const row = screen.getByRole("listitem");
    expect(within(row).getByText(formatDateTime(AT))).toBeInTheDocument();
    expect(within(row).getByText("sam")).toBeInTheDocument();
    expect(within(row).getByText("×1½")).toBeInTheDocument();
    expect(within(row).getByText("stock updated")).toBeInTheDocument();
  });

  it("falls back to a placeholder when `cooked_by` is null", () => {
    renderRow(log({ cooked_by: null }));
    expect(screen.getByText("Unknown cook")).toBeInTheDocument();
  });
});

describe("CookLogRow — no deduction", () => {
  it("shows 'stock not changed' with no accordion or table", () => {
    renderRow(log({ deducted: false, deductions: [] }));
    expect(
      screen.getByText("logged — stock not changed"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("CookLogRow — deduction accordion", () => {
  const fiveReasons = log({
    deductions: [
      ded("ok", "flour"),
      ded("clamped to 0", "butter"),
      ded("not in inventory", "vanilla"),
      ded("have uncertain (incompatible unit)", "milk"),
      ded("to taste", "salt", { requested: null, deducted: null }),
    ],
  });

  it("collapses to a reason summary and is closed by default", () => {
    renderRow(fiveReasons);
    const toggle = screen.getByRole("button", {
      name: /5 ingredients · 1 ran out · 1 not tracked · 1 to check/,
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("expands to a per-ingredient table with a chip for each of the five reasons", async () => {
    const user = userEvent.setup();
    renderRow(fiveReasons);

    await user.click(screen.getByRole("button", { name: /5 ingredients/ }));

    const table = screen.getByRole("table", {
      name: /per-ingredient stock change/i,
    });
    expect(screen.getByRole("button", { name: /5 ingredients/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    for (const chip of [
      "deducted",
      "ran out",
      "not tracked",
      "check what you have",
      "to taste",
    ]) {
      expect(within(table).getByText(chip)).toBeInTheDocument();
    }
    // requested → deducted, before → after, in the inventory unit
    expect(within(table).getAllByText("50 → 40 g").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("100 → 60 g").length).toBeGreaterThan(0);
  });

  it("guards a deducted flag that arrives with an empty deductions list", () => {
    renderRow(log({ deducted: true, deductions: [] }));
    // The on/off token still reads "stock updated", but with nothing to show
    // there is no accordion toggle and no table.
    expect(screen.getByText("stock updated")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("CookLogRow — recipe title", () => {
  it("is omitted by default (per-recipe panel)", () => {
    renderRow(log());
    expect(screen.queryByText("Buttermilk Pancakes")).not.toBeInTheDocument();
  });

  it("is shown when asked, with a deleted marker once `recipe_id` is null", () => {
    renderRow(log({ recipe_id: null }), true);
    expect(screen.getByText("Buttermilk Pancakes")).toBeInTheDocument();
    expect(screen.getByText(/recipe deleted/i)).toBeInTheDocument();
  });
});

describe("CookLogRow — forward only", () => {
  it("offers no undo affordance (R-12)", () => {
    renderRow(log());
    expect(screen.queryByText(/undo/i)).not.toBeInTheDocument();
  });
});

describe("deductionSummary", () => {
  it("lists only the non-zero reason counts", () => {
    expect(
      deductionSummary([
        ded("ok", "a"),
        ded("ok", "b"),
        ded("clamped to 0", "c"),
        ded("not in inventory", "d"),
        ded("have uncertain (incompatible unit)", "e"),
      ]),
    ).toBe("5 ingredients · 1 ran out · 1 not tracked · 1 to check");
  });

  it("is just a count when every ingredient deducted cleanly", () => {
    expect(deductionSummary([ded("ok", "a")])).toBe("1 ingredient");
  });
});
