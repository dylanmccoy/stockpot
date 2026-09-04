import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { sampleGroceryList, sampleRecipe } from "../test/handlers";
import { ToastProvider } from "../components";
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

function GroceryDetailStub() {
  const { id } = useParams();
  return <h1>grocery list {id}</h1>;
}

function renderList(path = "/") {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <Routes>
            <Route path="/" element={<RecipeList />} />
            <Route path="/recipes/new" element={<h1>New recipe</h1>} />
            <Route path="/recipes/:id" element={<h1>Recipe detail</h1>} />
            <Route path="/groceries/:id" element={<GroceryDetailStub />} />
          </Routes>
        </ToastProvider>
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

describe("RecipeList → grocery create dialog", () => {
  const enterSelect = () =>
    userEvent.click(screen.getByRole("button", { name: "Select" }));
  const tick = (name: string) =>
    userEvent.click(screen.getByRole("checkbox", { name }));
  const openDialog = () =>
    userEvent.click(
      screen.getByRole("button", { name: "Create grocery list" }),
    );
  const stepper = (recipeTitle: string) =>
    screen.getByRole("group", { name: `Multiplier for ${recipeTitle}` });

  it("collects a multiplier per recipe + a name, then POSTs the right body", async () => {
    useRecipes(threeRecipes);
    const bodies: unknown[] = [];
    server.use(
      http.post("/api/grocery", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(sampleGroceryList, { status: 201 });
      }),
    );

    const queryClient = renderList();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByText("Pad Thai");
    await enterSelect();
    await tick("Pad Thai");
    await tick("Bibimbap");
    await openDialog();

    // A row + Stepper per selected recipe, defaulting to 1×.
    expect(stepper("Pad Thai")).toBeInTheDocument();
    expect(stepper("Bibimbap")).toBeInTheDocument();

    // Bump Pad Thai to 2×; leave Bibimbap at the 1× default.
    await userEvent.click(
      within(stepper("Pad Thai")).getByRole("button", { name: "2" }),
    );
    await userEvent.type(screen.getByLabelText("List name"), "Weekend shop");
    await userEvent.click(screen.getByRole("button", { name: "Create list" }));

    // Success: confirmation toast + navigate to the new list.
    expect(
      await screen.findByText("Grocery list created."),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "grocery list 1" }),
    ).toBeInTheDocument();

    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toEqual({
      recipe_ids: [3, 2],
      multipliers: { "3": 2, "2": 1 },
      name: "Weekend shop",
    });

    // spec §10.5: the new list invalidates the /groceries index query.
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["grocery"] });
  });

  it("omits the name when left blank so the server default applies", async () => {
    useRecipes(threeRecipes);
    const bodies: Array<Record<string, unknown>> = [];
    server.use(
      http.post("/api/grocery", async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json(sampleGroceryList, { status: 201 });
      }),
    );

    renderList();
    await screen.findByText("Pad Thai");
    await enterSelect();
    await tick("Apple Pie");
    await openDialog();

    // Placeholder previews the server default; the field itself stays empty.
    expect(screen.getByLabelText("List name")).toHaveAttribute(
      "placeholder",
      expect.stringMatching(/^Groceries \d{4}-\d{2}-\d{2}$/),
    );
    await userEvent.click(screen.getByRole("button", { name: "Create list" }));

    await screen.findByText("Grocery list created.");
    expect(bodies[0]).not.toHaveProperty("name");
    expect(bodies[0].recipe_ids).toEqual([1]);
  });

  it("recovers from a 422 for a vanished recipe: drop it, resubmit, succeed", async () => {
    let recipesBody: RecipeRead[] = threeRecipes;
    let firstPost = true;
    const bodies: Array<{ recipe_ids: number[] }> = [];

    server.use(
      http.get("/api/recipes", () => HttpResponse.json(recipesBody)),
      http.post("/api/grocery", async ({ request }) => {
        bodies.push((await request.json()) as { recipe_ids: number[] });
        if (firstPost) {
          firstPost = false;
          // Pad Thai was deleted by someone else in the meantime.
          recipesBody = [bibimbap, applePie];
          return HttpResponse.json(
            { detail: "recipe 3 does not exist" },
            { status: 422 },
          );
        }
        return HttpResponse.json(sampleGroceryList, { status: 201 });
      }),
    );

    renderList();
    await screen.findByText("Pad Thai");
    await enterSelect();
    await tick("Pad Thai");
    await tick("Bibimbap");
    await openDialog();
    await userEvent.click(screen.getByRole("button", { name: "Create list" }));

    // Recovery path: names the gone recipe, offers to drop it.
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Pad Thai.*deleted/);
    await userEvent.click(
      within(alert).getByRole("button", { name: "Remove it and continue" }),
    );

    // Resubmit with the trimmed selection succeeds.
    await userEvent.click(screen.getByRole("button", { name: "Create list" }));
    expect(
      await screen.findByText("Grocery list created."),
    ).toBeInTheDocument();

    expect(bodies[0].recipe_ids).toEqual([3, 2]);
    expect(bodies[1].recipe_ids).toEqual([2]);
  });

  it("closing the dialog and re-opening resets multipliers and name", async () => {
    useRecipes(threeRecipes);
    renderList();
    await screen.findByText("Pad Thai");
    await enterSelect();
    await tick("Pad Thai");
    await openDialog();

    await userEvent.click(
      within(stepper("Pad Thai")).getByRole("button", { name: "3" }),
    );
    await userEvent.type(screen.getByLabelText("List name"), "Draft");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await openDialog();
    expect(screen.getByLabelText("List name")).toHaveValue("");
    expect(
      within(stepper("Pad Thai")).getByRole("button", { name: "1" }),
    ).toHaveAttribute("aria-pressed", "true");
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
