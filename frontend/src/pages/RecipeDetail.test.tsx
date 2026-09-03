import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { sampleRecipe } from "../test/handlers";
import { ToastProvider } from "../components";
import type { RecipeRead } from "../types";
import RecipeDetail, {
  asOpenableUrl,
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

  it("keeps an empty made-history placeholder panel", async () => {
    useRecipe(detailRecipe);
    renderDetail();
    await screen.findByRole("heading", { name: "Buttermilk Pancakes" });

    const panel = screen.getByRole("region", { name: "Made history" });
    expect(
      within(panel).getByRole("heading", { name: "Made history" }),
    ).toBeInTheDocument();
    expect(within(panel).queryByRole("listitem")).not.toBeInTheDocument();
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
