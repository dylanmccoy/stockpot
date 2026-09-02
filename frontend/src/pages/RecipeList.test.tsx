import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { sampleRecipe } from "../test/handlers";
import type { RecipeRead } from "../types";
import RecipeList, {
  filterByFacets,
  searchRecipes,
  sortRecipes,
} from "./RecipeList";

function makeRecipe(over: Partial<RecipeRead>): RecipeRead {
  return { ...sampleRecipe, ...over };
}

// Server order is `created_at DESC, id DESC` — this array is already "newest".
const padThai = makeRecipe({
  id: 3,
  title: "Pad Thai",
  cuisine: "Thai",
  tags: ["noodles", "dinner"],
  updated_at: "2026-08-01T00:00:00+00:00",
  prep_time: 20,
  cook_time: 15,
});
const bibimbap = makeRecipe({
  id: 2,
  title: "Bibimbap",
  cuisine: "Korean",
  tags: ["rice", "dinner"],
  updated_at: "2026-09-05T00:00:00+00:00",
});
const applePie = makeRecipe({
  id: 1,
  title: "Apple Pie",
  cuisine: "American",
  tags: ["dessert"],
  updated_at: "2026-07-01T00:00:00+00:00",
});
const threeRecipes = [padThai, bibimbap, applePie];

function useRecipes(list: RecipeRead[]) {
  server.use(http.get("/api/recipes", () => HttpResponse.json(list)));
}

function renderList(path = "/") {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<RecipeList />} />
          <Route path="/recipes/new" element={<h1>New recipe</h1>} />
          <Route path="/recipes/:id" element={<h1>Recipe detail</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

const cardTitles = () =>
  screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);

describe("RecipeList", () => {
  it("renders recipes from the ['recipes'] query, in server order", async () => {
    useRecipes(threeRecipes);
    renderList();
    expect(await screen.findByText("Pad Thai")).toBeInTheDocument();
    expect(cardTitles()).toEqual(["Pad Thai", "Bibimbap", "Apple Pie"]);
  });

  it("free-text search narrows by title, cuisine, or tag", async () => {
    useRecipes(threeRecipes);
    renderList();
    await screen.findByText("Pad Thai");
    const search = screen.getByLabelText("Search recipes");

    await userEvent.type(search, "korean"); // cuisine match
    expect(cardTitles()).toEqual(["Bibimbap"]);

    await userEvent.clear(search);
    await userEvent.type(search, "dessert"); // tag match
    expect(cardTitles()).toEqual(["Apple Pie"]);

    await userEvent.clear(search);
    await userEvent.type(search, "pad"); // title match
    expect(cardTitles()).toEqual(["Pad Thai"]);
  });

  it("a cuisine facet and a tag facet intersect", async () => {
    useRecipes(threeRecipes);
    renderList();
    await screen.findByText("Pad Thai");

    await userEvent.click(screen.getByRole("checkbox", { name: "Thai" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "dinner" }));

    // tag "dinner" alone → {Pad Thai, Bibimbap}; cuisine "Thai" trims to one.
    expect(cardTitles()).toEqual(["Pad Thai"]);
  });

  it("re-sort reorders the list", async () => {
    useRecipes(threeRecipes);
    renderList();
    await screen.findByText("Pad Thai");
    const sort = screen.getByLabelText("Sort");

    await userEvent.selectOptions(sort, "Title A–Z");
    expect(cardTitles()).toEqual(["Apple Pie", "Bibimbap", "Pad Thai"]);

    await userEvent.selectOptions(sort, "Recently updated");
    expect(cardTitles()).toEqual(["Bibimbap", "Pad Thai", "Apple Pie"]);
  });

  it("shows the empty state when there are no recipes", async () => {
    useRecipes([]);
    renderList();
    expect(await screen.findByText(/no recipes yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Add your first recipe" }),
    ).toHaveAttribute("href", "/recipes/new");
  });

  it("opens a recipe when its card is clicked", async () => {
    useRecipes(threeRecipes);
    renderList();
    await userEvent.click(await screen.findByText("Pad Thai"));
    expect(
      await screen.findByRole("heading", { name: "Recipe detail" }),
    ).toBeInTheDocument();
  });

  it("the add-recipe action goes to /recipes/new", async () => {
    useRecipes(threeRecipes);
    renderList();
    await userEvent.click(
      await screen.findByRole("link", { name: "Add recipe" }),
    );
    expect(
      await screen.findByRole("heading", { name: "New recipe" }),
    ).toBeInTheDocument();
  });

  it("surfaces a query failure with a retry affordance", async () => {
    server.use(errorHandlers.serverError("get", "/api/recipes"));
    renderList();
    const panel = await screen.findByRole("alert");
    expect(
      within(panel).getByRole("button", { name: "Retry" }),
    ).toBeInTheDocument();
  });
});

describe("RecipeList multi-select", () => {
  const checkbox = (name: string) =>
    screen.getByRole("checkbox", { name }) as HTMLInputElement;
  const createButton = () =>
    screen.queryByRole("button", { name: "Create grocery list" });
  const count = () => screen.getByRole("status").textContent;

  it("gathers recipes into a sticky bar and clears on exit", async () => {
    useRecipes(threeRecipes);
    renderList();
    await screen.findByText("Pad Thai");

    // No selection UI until the mode is entered.
    expect(createButton()).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Select" }));

    await userEvent.click(checkbox("Pad Thai"));
    await userEvent.click(checkbox("Bibimbap"));

    expect(count()).toBe("2 selected");
    expect(createButton()).toBeInTheDocument();

    // Untick both → the bar disappears.
    await userEvent.click(checkbox("Pad Thai"));
    await userEvent.click(checkbox("Bibimbap"));
    expect(count()).toBe("");
    expect(createButton()).not.toBeInTheDocument();

    // Re-select, then leave the mode → selection is dropped.
    await userEvent.click(checkbox("Pad Thai"));
    expect(count()).toBe("1 selected");
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(count()).toBe("");

    await userEvent.click(screen.getByRole("button", { name: "Select" }));
    expect(checkbox("Pad Thai").checked).toBe(false);
  });

  it("tapping a card ticks it instead of navigating", async () => {
    useRecipes(threeRecipes);
    renderList();
    await screen.findByText("Pad Thai");
    await userEvent.click(screen.getByRole("button", { name: "Select" }));

    await userEvent.click(screen.getByText("Pad Thai"));

    expect(count()).toBe("1 selected");
    expect(checkbox("Pad Thai").checked).toBe(true);
    expect(
      screen.getByRole("heading", { name: "Recipes" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Recipe detail" }),
    ).not.toBeInTheDocument();
  });
});

describe("RecipeList pure helpers", () => {
  it("searchRecipes matches title / cuisine / tag, case-insensitively", () => {
    expect(searchRecipes(threeRecipes, "  ").map((r) => r.id)).toEqual([
      3, 2, 1,
    ]);
    expect(searchRecipes(threeRecipes, "THAI").map((r) => r.id)).toEqual([3]);
    expect(searchRecipes(threeRecipes, "rice").map((r) => r.id)).toEqual([2]);
  });

  it("filterByFacets unions within a facet and intersects across facets", () => {
    expect(
      filterByFacets(threeRecipes, {
        cuisines: ["Thai", "Korean"],
        tags: [],
      }).map((r) => r.id),
    ).toEqual([3, 2]);
    expect(
      filterByFacets(threeRecipes, {
        cuisines: ["Korean"],
        tags: ["dinner"],
      }).map((r) => r.id),
    ).toEqual([2]);
  });

  it("sortRecipes keeps server order for 'newest' and does not mutate input", () => {
    const input = [...threeRecipes];
    const byTitle = sortRecipes(input, "title");
    expect(byTitle.map((r) => r.title)).toEqual([
      "Apple Pie",
      "Bibimbap",
      "Pad Thai",
    ]);
    expect(sortRecipes(input, "updated").map((r) => r.id)).toEqual([2, 3, 1]);
    expect(sortRecipes(input, "newest")).toEqual(input);
    expect(input).toEqual(threeRecipes);
  });
});
