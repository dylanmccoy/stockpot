import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import {
  makeCookLog,
  makeDeduction,
  sampleCookLog,
  sampleRecipe,
} from "../test/handlers";
import { ToastProvider } from "../components";
import type { AvailabilityReport, CookLogRead, RecipeRead } from "../types";
import RecipeDetail, {
  amountLabel,
  asOpenableUrl,
  groupAvailabilityLines,
  scaledQuantityLabel,
} from "./RecipeDetail";

// ── fixture ──────────────────────────────────────────────────────────────────

const detailRecipe: RecipeRead = {
  ...sampleRecipe,
  id: 1,
  title: "Buttermilk Pancakes",
  notes: "Rest the batter 10 minutes.",
  prep_time: 5,
  cook_time: 10,
  servings: 4,
  cuisine: "American",
  source_url: "https://example.com/pancakes",
  tags: ["breakfast"],
  steps: ["Whisk the dry", "Fold in the wet", "Griddle"],
  // Deliberately out of position order — the screen must sort by `position`.
  ingredients: [
    {
      id: 12,
      position: 2,
      quantity: null,
      unit: null,
      item: "salt",
      note: "to taste",
      normalized_name: "salt",
      raw_text: null,
    },
    {
      id: 10,
      position: 0,
      quantity: 2,
      unit: "cups",
      item: "flour",
      note: null,
      normalized_name: "flour",
      raw_text: null,
    },
    {
      id: 11,
      position: 1,
      quantity: 1 / 3,
      unit: "cup",
      item: "sugar",
      note: null,
      normalized_name: "sugar",
      raw_text: null,
    },
  ],
};

function useRecipe(recipe: RecipeRead) {
  server.use(http.get("/api/recipes/:id", () => HttpResponse.json(recipe)));
}

function useCookLogs(logs: CookLogRead[]) {
  server.use(
    http.get("/api/recipes/:id/cook-logs", () => HttpResponse.json(logs)),
  );
}

const AT = "2026-08-30T09:00:00+00:00";

const dedFixture = makeDeduction;

const cookLogFixture = (overrides: Partial<CookLogRead> = {}): CookLogRead =>
  makeCookLog({ id: 100, cooked_at: AT, ...overrides });

function renderDetail(path = "/recipes/1") {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <nav>
            <Link to="/recipes/1">open 1</Link>
            <Link to="/recipes/2">open 2</Link>
          </nav>
          <Routes>
            <Route path="/" element={<p>home</p>} />
            <Route path="/recipes/:id" element={<RecipeDetail />} />
            <Route path="/recipes/:id/edit" element={<p>edit page</p>} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

const ingredientRegion = () =>
  screen.getByRole("region", { name: "Ingredients" });

// ── pure helpers ─────────────────────────────────────────────────────────────

describe("scaledQuantityLabel", () => {
  it("scales by the multiplier and formats — never a raw float", () => {
    expect(scaledQuantityLabel({ quantity: 2, unit: "cups" }, 1)).toBe(
      "2 cups",
    );
    expect(scaledQuantityLabel({ quantity: 1 / 3, unit: "cup" }, 1)).toBe(
      "⅓ cup",
    );
    expect(scaledQuantityLabel({ quantity: 1 / 3, unit: "cup" }, 2)).toBe(
      "⅔ cup",
    );
    expect(scaledQuantityLabel({ quantity: 2, unit: "cups" }, 3)).toBe(
      "6 cups",
    );
  });

  it("a count unit drops the unit token; to-taste is blank", () => {
    expect(scaledQuantityLabel({ quantity: 3, unit: null }, 1)).toBe("3");
    expect(scaledQuantityLabel({ quantity: 3, unit: "unit" }, 1)).toBe("3");
    expect(scaledQuantityLabel({ quantity: 1.5, unit: "each" }, 2)).toBe("3");
    expect(scaledQuantityLabel({ quantity: null, unit: null }, 5)).toBe("");
  });
});

describe("asOpenableUrl", () => {
  it("accepts http(s), rejects everything else and null", () => {
    expect(asOpenableUrl("https://example.com/r")).toBe(
      "https://example.com/r",
    );
    expect(asOpenableUrl("  http://example.com  ")).toBe("http://example.com/");
    expect(asOpenableUrl("ftp://example.com")).toBeNull();
    expect(asOpenableUrl("from grandma")).toBeNull();
    expect(asOpenableUrl(null)).toBeNull();
  });
});

// ── availability fixture ─────────────────────────────────────────────────────

// 7 lines → 6 rows: the two butter members share a `group_key` (spec §10.4,
// dedupe). `all_available: false` with 3 distinct short/uncertain/missing
// groups → banner "Missing 3 items".
const availabilityReport: AvailabilityReport = {
  recipe_id: 1,
  multiplier: 1,
  all_available: false,
  lines: [
    {
      ingredient_id: 1,
      item: "butter",
      need: 100,
      need_unit: "g",
      group_key: "butter|mass",
      group_unit: "g",
      group_need: 150,
      group_have: 200,
      group_short: 0,
      status: "ok",
      nettable: true,
    },
    {
      ingredient_id: 2,
      item: "unsalted butter",
      need: 50,
      need_unit: "g",
      group_key: "butter|mass",
      group_unit: "g",
      group_need: 150,
      group_have: 200,
      group_short: 0,
      status: "ok",
      nettable: true,
    },
    {
      ingredient_id: 3,
      item: "flour",
      need: 200,
      need_unit: "g",
      group_key: "flour|mass",
      group_unit: "g",
      group_need: 200,
      group_have: 500,
      group_short: 0,
      status: "ok",
      nettable: true,
    },
    {
      ingredient_id: 4,
      item: "sugar",
      need: 200,
      need_unit: "g",
      group_key: "sugar|mass",
      group_unit: "g",
      group_need: 200,
      group_have: 50,
      group_short: 150,
      status: "short",
      nettable: true,
    },
    {
      ingredient_id: 5,
      item: "milk",
      need: 300,
      need_unit: "ml",
      group_key: "milk|volume",
      group_unit: "ml",
      group_need: 300,
      group_have: 100,
      group_short: 100,
      status: "have_uncertain",
      nettable: false,
    },
    {
      ingredient_id: 6,
      item: "vanilla",
      need: 5,
      need_unit: "ml",
      group_key: "vanilla|volume",
      group_unit: "ml",
      group_need: 5,
      group_have: 0,
      group_short: 5,
      status: "missing",
      nettable: false,
    },
    {
      ingredient_id: 7,
      item: "salt",
      need: null,
      need_unit: "g",
      group_key: "salt|mass",
      group_unit: "g",
      group_need: null,
      group_have: null,
      group_short: null,
      status: "to_taste",
      nettable: false,
    },
  ],
};

function useAvailability(report: AvailabilityReport) {
  server.use(
    http.get("/api/recipes/:id/availability", () => HttpResponse.json(report)),
  );
}

describe("groupAvailabilityLines", () => {
  it("collapses lines sharing a group_key into one row, keeping order", () => {
    const rows = groupAvailabilityLines(availabilityReport.lines);
    expect(rows.map((r) => r.item)).toEqual([
      "butter, unsalted butter",
      "flour",
      "sugar",
      "milk",
      "vanilla",
      "salt",
    ]);
  });

  it("labels each status per §7.4; shortfall amount only on 'short'", () => {
    const byItem = Object.fromEntries(
      groupAvailabilityLines(availabilityReport.lines).map((r) => [r.item, r]),
    );
    expect(byItem["flour"].statusLabel).toBe("Have it");
    expect(byItem["flour"].needLabel).toBe("200 g");
    expect(byItem["sugar"].statusLabel).toBe("Short 150 g");
    expect(byItem["milk"].statusLabel).toBe("Check what you have");
    expect(byItem["vanilla"].statusLabel).toBe("Missing");
    expect(byItem["salt"].statusLabel).toBe("To taste");
    expect(byItem["salt"].needLabel).toBe("—");
  });

  it("keeps to-taste and quantified members of the same group visible", () => {
    const rows = groupAvailabilityLines([
      {
        ingredient_id: 1,
        item: "salt to taste",
        need: null,
        need_unit: "g",
        group_key: "salt|mass",
        group_unit: "g",
        group_need: null,
        group_have: null,
        group_short: null,
        status: "to_taste",
        nettable: false,
      },
      {
        ingredient_id: 2,
        item: "salt for brine",
        need: 20,
        need_unit: "g",
        group_key: "salt|mass",
        group_unit: "g",
        group_need: 20,
        group_have: 5,
        group_short: 15,
        status: "short",
        nettable: true,
      },
    ]);

    expect(rows).toHaveLength(2);
    expect(rows.map((row) => [row.item, row.statusLabel, row.needLabel])).toEqual(
      [
        ["salt to taste", "To taste", "—"],
        ["salt for brine", "Short 15 g", "20 g"],
      ],
    );
    expect(new Set(rows.map((row) => row.groupKey))).toHaveLength(2);
  });
});

describe("amountLabel", () => {
  it("appends the unit word, drops it for count units, empty for null", () => {
    expect(amountLabel(150, "g")).toBe("150 g");
    expect(amountLabel(3, null)).toBe("3");
    expect(amountLabel(2, "unit")).toBe("2");
    expect(amountLabel(null, "g")).toBe("");
  });
});

// ── body ─────────────────────────────────────────────────────────────────────

describe("RecipeDetail body", () => {
  it("renders ingredients in order with formatted quantities and the meta", async () => {
    useRecipe(detailRecipe);
    renderDetail();

    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const rows = within(ingredientRegion()).getAllByRole("listitem");
    expect(rows.map((li) => li.textContent)).toEqual([
      "2 cupsflour",
      "⅓ cupsugar",
      "saltto taste",
    ]);

    expect(screen.getByText("American")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("5 min")).toBeInTheDocument();
    expect(screen.getByText("10 min")).toBeInTheDocument();

    expect(
      within(screen.getByRole("region", { name: "Steps" })).getAllByRole(
        "listitem",
      ),
    ).toHaveLength(3);
    expect(screen.getByText("Rest the batter 10 minutes.")).toBeInTheDocument();
  });

  it("offers an open-link only for a valid source URL", async () => {
    useRecipe(detailRecipe);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    expect(
      screen.getByRole("link", { name: "Open source link" }),
    ).toHaveAttribute("href", "https://example.com/pancakes");
  });

  it("shows a non-URL source as plain text", async () => {
    useRecipe({ ...detailRecipe, source_url: "from a friend" });
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    expect(screen.getByText("Source: from a friend")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Open source link" }),
    ).not.toBeInTheDocument();
  });

  it("shows an empty made-history panel before the first cook", async () => {
    useRecipe(detailRecipe);
    useCookLogs([]);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const panel = screen.getByRole("region", { name: "Made history" });
    expect(
      await within(panel).findByText("Cook this recipe to start its history."),
    ).toBeInTheDocument();
    expect(within(panel).queryByRole("listitem")).not.toBeInTheDocument();
  });
});

// ── made history (per-recipe panel, spec §10.8) ──────────────────────────────

const historyRegion = () => screen.getByRole("region", { name: "Made history" });

describe("RecipeDetail made history", () => {
  it("lists cooks from `[recipe-cook-logs, id]`, newest first, with a count header", async () => {
    useRecipe(detailRecipe);
    // Deliberately handed to the panel oldest-first; the multiplier tags which
    // cook is which without depending on the test machine's timezone.
    useCookLogs([
      cookLogFixture({
        id: 1,
        multiplier: 3,
        cooked_at: "2026-08-01T00:00:00+00:00",
      }),
      cookLogFixture({
        id: 2,
        multiplier: 7,
        cooked_at: "2026-08-20T00:00:00+00:00",
      }),
    ]);
    const queryClient = renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const panel = historyRegion();
    expect(
      await within(panel).findByText(/Cooked 2 times · last/),
    ).toBeInTheDocument();

    const rows = within(panel).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    // id 2 is the newer cook — it must render first.
    expect(rows[0]).toHaveTextContent("×7");
    expect(rows[1]).toHaveTextContent("×3");

    expect(
      queryClient.getQueryData(["recipe-cook-logs", 1]),
    ).toHaveLength(2);
  });

  it("a no-deduction cook shows 'stock not changed' and no detail table", async () => {
    useRecipe(detailRecipe);
    useCookLogs([cookLogFixture({ deducted: false, deductions: [] })]);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const panel = historyRegion();
    expect(
      await within(panel).findByText("logged — stock not changed"),
    ).toBeInTheDocument();
    expect(within(panel).queryByRole("table")).not.toBeInTheDocument();
    expect(within(panel).queryByRole("button")).not.toBeInTheDocument();
  });

  it("expands a deducted cook to a chip for each of the five reasons (flow vs MSW)", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    useCookLogs([
      cookLogFixture({
        id: 5,
        deducted: true,
        deductions: [
          dedFixture("ok", "flour"),
          dedFixture("clamped to 0", "butter"),
          dedFixture("not in inventory", "vanilla"),
          dedFixture("have uncertain (incompatible unit)", "milk"),
          dedFixture("to taste", "salt"),
        ],
      }),
    ]);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const panel = historyRegion();
    await user.click(
      await within(panel).findByRole("button", { name: /5 ingredients/ }),
    );

    const table = within(panel).getByRole("table", {
      name: /per-ingredient stock change/i,
    });
    for (const chip of [
      "deducted",
      "ran out",
      "not tracked",
      "check what you have",
      "to taste",
    ]) {
      expect(within(table).getByText(chip)).toBeInTheDocument();
    }
  });

  it("offers a retry when the history call fails", async () => {
    useRecipe(detailRecipe);
    server.use(
      errorHandlers.serverError("get", "/api/recipes/:id/cook-logs"),
    );
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const panel = historyRegion();
    expect(
      await within(panel).findByText("Couldn’t load this recipe’s history."),
    ).toBeInTheDocument();
    expect(
      within(panel).getByRole("button", { name: "Retry" }),
    ).toBeInTheDocument();
  });
});

// ── multiplier ───────────────────────────────────────────────────────────────

describe("RecipeDetail multiplier", () => {
  it("rescales displayed quantities on a preset and on free input", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    await user.click(screen.getByRole("button", { name: "3" }));
    let rows = within(ingredientRegion()).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("6 cupsflour");
    expect(rows[1]).toHaveTextContent("1 cupsugar");

    const exact = screen.getByLabelText("Exact value");
    await user.clear(exact);
    await user.type(exact, "2");
    await user.tab();

    rows = within(ingredientRegion()).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("4 cupsflour");
    expect(rows[1]).toHaveTextContent("⅔ cupsugar");
  });

  it("resets to 1 on every visit to the screen", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/recipes/:id", ({ params }) =>
        HttpResponse.json(
          Number(params.id) === 2
            ? { ...detailRecipe, id: 2, title: "Waffles" }
            : detailRecipe,
        ),
      ),
    );
    renderDetail("/recipes/1");
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    await user.click(screen.getByRole("button", { name: "3" }));
    expect(screen.getByLabelText("Exact value")).toHaveValue(3);

    await user.click(screen.getByRole("link", { name: "open 2" }));
    await screen.findByRole("heading", { name: "Waffles" });

    expect(screen.getByLabelText("Exact value")).toHaveValue(1);
    expect(
      within(ingredientRegion()).getAllByRole("listitem")[0],
    ).toHaveTextContent("2 cupsflour");
  });
});

// ── delete + not-found ───────────────────────────────────────────────────────

describe("RecipeDetail delete", () => {
  it("confirms, deletes, and navigates to the list", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    let deleted = false;
    server.use(
      http.delete("/api/recipes/:id", () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    await user.click(screen.getByRole("button", { name: "Delete recipe" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    expect(await screen.findByText("home")).toBeInTheDocument();
    expect(deleted).toBe(true);
  });

  it("cancel keeps the recipe on screen", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    await user.click(screen.getByRole("button", { name: "Delete recipe" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Buttermilk Pancakes" }),
    ).toBeInTheDocument();
  });
});

describe("RecipeDetail not-found", () => {
  it("shows an in-content not-found panel with a link back to the list", async () => {
    server.use(errorHandlers.notFound("get", "/api/recipes/:id"));
    renderDetail("/recipes/999");

    await screen.findByRole("heading", { name: "Recipe not found" });
    expect(
      screen.getByRole("link", { name: "Back to recipes" }),
    ).toHaveAttribute("href", "/");
  });
});

// ── availability table ───────────────────────────────────────────────────────

const availabilityRegion = () =>
  screen.getByRole("region", { name: "Availability" });

const availabilityTable = () =>
  within(availabilityRegion()).findByRole("table");

// Match on the Ingredient cell's comma-separated members so "salt" doesn't
// also hit an "unsalted butter" group.
const rowFor = (table: HTMLElement, item: string) =>
  within(table)
    .getAllByRole("row")
    .find((r) =>
      within(r)
        .queryAllByRole("cell")[0]
        ?.textContent?.split(", ")
        .includes(item),
    );

describe("RecipeDetail availability", () => {
  it("renders a per-ingredient table, deduped by group, one status each", async () => {
    useRecipe(detailRecipe);
    useAvailability(availabilityReport);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const table = await availabilityTable();
    expect(within(table).getAllByRole("row").slice(1)).toHaveLength(6);

    const flour = rowFor(table, "flour")!;
    expect(flour).toHaveTextContent("200 g");
    expect(flour).toHaveTextContent("Have it");

    expect(rowFor(table, "sugar")).toHaveTextContent("Short 150 g");
    expect(rowFor(table, "vanilla")).toHaveTextContent("Missing");
    expect(rowFor(table, "salt")).toHaveTextContent("To taste");

    // the two butter members collapse to a single row
    expect(rowFor(table, "butter")).toBe(rowFor(table, "unsalted butter"));
    expect(rowFor(table, "butter")).toBeDefined();
  });

  it("marks an incomparable-unit line 'Check what you have' — explanation, no number", async () => {
    useRecipe(detailRecipe);
    useAvailability(availabilityReport);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const milk = rowFor(await availabilityTable(), "milk")!;
    expect(within(milk).getByText("Check what you have")).toBeInTheDocument();
    expect(
      within(milk).getByText(/unit we can.t compare/i),
    ).toBeInTheDocument();
    // group_short (100) must never surface for this status (§7.4)
    expect(milk).not.toHaveTextContent("100");
  });

  it("banner says everything is available", async () => {
    useRecipe(detailRecipe);
    useAvailability({
      ...availabilityReport,
      all_available: true,
      lines: [availabilityReport.lines[2]],
    });
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    expect(
      await within(availabilityRegion()).findByText("You have everything"),
    ).toBeInTheDocument();
  });

  it("banner counts short + missing groups, not the incomparable-unit ones", async () => {
    useRecipe(detailRecipe);
    useAvailability(availabilityReport); // 1 short + 1 missing + 1 have_uncertain
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    expect(
      await within(availabilityRegion()).findByText("Missing 2 items"),
    ).toBeInTheDocument();
  });

  it("banner prompts a check when the only gaps are incomparable-unit rows", async () => {
    useRecipe(detailRecipe);
    useAvailability({
      ...availabilityReport,
      all_available: false,
      lines: [availabilityReport.lines[4]], // milk, have_uncertain
    });
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    // banner (a <p>), distinct from the milk row's status badge of the same text
    expect(
      await within(availabilityRegion()).findByText("Check what you have", {
        selector: "p",
      }),
    ).toBeInTheDocument();
  });

  it("re-queries and rescales the table when the multiplier changes", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    server.use(
      http.get("/api/recipes/:id/availability", ({ request }) => {
        const m = Number(
          new URL(request.url).searchParams.get("multiplier") ?? "1",
        );
        return HttpResponse.json({
          ...availabilityReport,
          multiplier: m,
          lines: availabilityReport.lines.map((l) => ({
            ...l,
            need: l.need == null ? null : l.need * m,
            group_need: l.group_need == null ? null : l.group_need * m,
            group_short: l.group_short == null ? null : l.group_short * m,
          })),
        });
      }),
    );
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const flourNeed = async () =>
      rowFor(await availabilityTable(), "flour")!.textContent;

    await waitFor(async () => expect(await flourNeed()).toContain("200 g"));

    await user.click(screen.getByRole("button", { name: "2" }));

    await waitFor(async () => expect(await flourNeed()).toContain("400 g"));
  });

  it("offers a retry when the availability call fails", async () => {
    useRecipe(detailRecipe);
    server.use(
      errorHandlers.serverError("get", "/api/recipes/:id/availability"),
    );
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const region = availabilityRegion();
    expect(
      await within(region).findByText("Couldn’t check availability."),
    ).toBeInTheDocument();
    expect(
      within(region).getByRole("button", { name: "Retry" }),
    ).toBeInTheDocument();
  });
});

// ── cook action ──────────────────────────────────────────────────────────────

const cookRegion = () => screen.getByRole("region", { name: "Cook" });

const cookButton = () =>
  within(cookRegion()).getByRole("button", { name: /mark as cooked/i });

const deductToggle = () =>
  within(cookRegion()).getByRole("checkbox", {
    name: /deduct from inventory/i,
  });

/** Capture the JSON body of the next cook POST. */
function captureCook(): { body: () => unknown } {
  let body: unknown;
  server.use(
    http.post("/api/recipes/:id/cook", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json(sampleCookLog, { status: 201 });
    }),
  );
  return { body: () => body };
}

/** Count availability GETs so a post-cook refetch is observable. */
function countAvailability(): { calls: () => number } {
  let calls = 0;
  server.use(
    http.get("/api/recipes/:id/availability", () => {
      calls += 1;
      return HttpResponse.json(availabilityReport);
    }),
  );
  return { calls: () => calls };
}

describe("RecipeDetail cook", () => {
  it("shows a mark-as-cooked button and a deduct toggle on by default", async () => {
    useRecipe(detailRecipe);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    expect(cookButton()).toBeInTheDocument();
    expect(deductToggle()).toBeChecked();
  });

  it("posts at the current multiplier with deduct on by default", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    const cook = captureCook();
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    await user.click(screen.getByRole("button", { name: "2" }));
    await user.click(cookButton());

    await waitFor(() =>
      expect(cook.body()).toEqual({ multiplier: 2, deduct: true }),
    );
  });

  it("a cleared toggle posts deduct:false and softens the button copy", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    const cook = captureCook();
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    await user.click(deductToggle());
    await user.click(
      within(cookRegion()).getByRole("button", { name: "Mark as cooked" }),
    );

    await waitFor(() =>
      expect(cook.body()).toEqual({ multiplier: 1, deduct: false }),
    );
  });

  it("on success, refetches availability and invalidates the stock + history views", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    const avail = countAvailability();
    const queryClient = renderDetail();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });
    await waitFor(() => expect(avail.calls()).toBe(1));

    await user.click(cookButton());

    await waitFor(() => expect(avail.calls()).toBe(2));
    const keys = invalidate.mock.calls.map(
      (c) => (c[0] as { queryKey?: unknown[] } | undefined)?.queryKey,
    );
    expect(keys).toContainEqual(["availability", 1]);
    expect(keys).toContainEqual(["inventory"]);
    expect(keys).toContainEqual(["cook-logs"]);
    expect(keys).toContainEqual(["recipe-cook-logs", 1]);
  });

  it("on a 409 stock collision, toasts a retry message and refetches", async () => {
    const user = userEvent.setup();
    useRecipe(detailRecipe);
    const avail = countAvailability();
    server.use(errorHandlers.conflict("post", "/api/recipes/:id/cook"));
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });
    await waitFor(() => expect(avail.calls()).toBe(1));

    await user.click(cookButton());

    expect(
      await screen.findByText(
        "Someone else was updating stock. We've refreshed — try again.",
      ),
    ).toBeInTheDocument();
    await waitFor(() => expect(avail.calls()).toBe(2));
  });

  it("offers no undo affordance", async () => {
    useRecipe(detailRecipe);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    expect(
      screen.queryByRole("button", { name: /undo/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/undo/i)).not.toBeInTheDocument();
  });
});
