import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { Link, MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { server } from "../test/server";
import { makeQueryClient } from "../test/helpers";
import { sampleRecipe } from "../test/handlers";
import { ToastProvider } from "../components";
import { parseIngredientLine } from "../lib/parseIngredientLine";
import type { RecipeIngredientRead, RecipeRead, RecipeUpdate } from "../types";
import RecipeForm, {
  asOpenableUrl,
  buildRecipeCreate,
  ingredientRowsToSubmit,
  recipeToState,
  type IngredientDraft,
  type RecipeFormState,
} from "./RecipeForm";

/** A hand-entered ingredient row for the serialization fixtures. */
function manualRow(over: Partial<IngredientDraft>): IngredientDraft {
  return {
    uid: "r?",
    quantity: "",
    unit: "",
    item: "",
    note: "",
    origin: "manual",
    pristine: false,
    raw: "",
    ...over,
  };
}

/** A minimal valid draft; tests override `ingredients`. */
function baseState(): RecipeFormState {
  return {
    title: "R",
    cuisine: "",
    servings: "",
    prepTime: "",
    cookTime: "",
    sourceUrl: "",
    notes: "",
    tags: [],
    steps: [],
    ingredients: [],
  };
}

function RecipeLanding() {
  const { id } = useParams();
  return <p data-testid="recipe-landing">recipe {id}</p>;
}

function renderForm() {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/recipes/new"]}>
        <ToastProvider>
          <Routes>
            <Route path="/recipes/new" element={<RecipeForm mode="create" />} />
            <Route path="/recipes/:id" element={<RecipeLanding />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

// ── pure serialization (the single draft → POST-body seam) ─────────────────

describe("buildRecipeCreate", () => {
  const base: RecipeFormState = {
    title: "  Sheet Pan Chicken  ",
    cuisine: "  ",
    servings: "",
    prepTime: "15",
    cookTime: "",
    sourceUrl: "  not a url  ",
    notes: "line one\nline two",
    tags: ["dinner", "sheet-pan"],
    steps: [
      { uid: "s1", text: "  Heat the oven  " },
      { uid: "s2", text: "   " },
    ],
    ingredients: [
      manualRow({
        uid: "r1",
        quantity: "2",
        unit: "lb",
        item: "chicken thighs",
        note: "bone-in",
      }),
      manualRow({ uid: "r2", item: "kosher salt" }),
      manualRow({ uid: "r3" }),
    ],
  };

  it("trims scalars, drops blank optionals to null, and coerces numbers", () => {
    const body = buildRecipeCreate(base);
    expect(body).toMatchObject({
      title: "Sheet Pan Chicken",
      cuisine: null,
      source_url: "not a url", // stored verbatim, never validated
      prep_time: 15,
      cook_time: null,
      servings: null,
      notes: "line one\nline two",
      tags: ["dinner", "sheet-pan"],
    });
  });

  it("keeps only non-blank steps, in order", () => {
    expect(buildRecipeCreate(base).steps).toEqual(["Heat the oven"]);
  });

  it("emits one object element per content row; blank quantity => to-taste", () => {
    expect(buildRecipeCreate(base).ingredients).toEqual([
      { item: "chicken thighs", quantity: 2, unit: "lb", note: "bone-in" },
      { item: "kosher salt" },
    ]);
  });

  it("ingredientRowsToSubmit is the index space server errors point into", () => {
    expect(ingredientRowsToSubmit(base).map((r) => r.uid)).toEqual([
      "r1",
      "r2",
    ]);
  });
});

describe("buildRecipeCreate — mixed pasted / edited ingredients", () => {
  const pasteRow = (over: Partial<IngredientDraft>): IngredientDraft => ({
    ...manualRow(over),
    origin: "paste",
    pristine: over.pristine ?? true,
  });

  it("serializes an untouched pasted row as its raw string", () => {
    const state = {
      ...baseState(),
      ingredients: [
        pasteRow({
          uid: "p1",
          quantity: "2",
          unit: "tbsp",
          item: "olive oil",
          raw: "2 tbsp olive oil",
        }),
      ],
    };
    expect(buildRecipeCreate(state).ingredients).toEqual(["2 tbsp olive oil"]);
  });

  it("serializes an edited pasted row (pristine cleared) as an object", () => {
    const state = {
      ...baseState(),
      ingredients: [
        pasteRow({
          uid: "p1",
          quantity: "1",
          unit: "",
          item: "onion, diced and chopped",
          raw: "1 onion, diced",
          pristine: false,
        }),
      ],
    };
    expect(buildRecipeCreate(state).ingredients).toEqual([
      { item: "onion, diced and chopped", quantity: 1 },
    ]);
  });

  it("keeps both element kinds in one array, in row order", () => {
    const state = {
      ...baseState(),
      ingredients: [
        pasteRow({ uid: "p1", item: "olive oil", raw: "2 tbsp olive oil" }),
        pasteRow({
          uid: "p2",
          quantity: "1",
          item: "garlic",
          raw: "1 garlic",
          pristine: false,
        }),
        manualRow({ uid: "m1", item: "kosher salt" }),
      ],
    };
    expect(buildRecipeCreate(state).ingredients).toEqual([
      "2 tbsp olive oil",
      { item: "garlic", quantity: 1 },
      { item: "kosher salt" },
    ]);
  });
});

// ── pure seeding: RecipeRead → edit draft (spec §10.3) ────────────────────────

describe("recipeToState", () => {
  it("maps scalars and nulls and clones tags / steps into uid'd drafts", () => {
    const s = recipeToState({
      ...sampleRecipe,
      cuisine: null,
      servings: null,
      source_url: null,
    });
    expect(s).toMatchObject({
      title: "Buttermilk Pancakes",
      cuisine: "",
      servings: "",
      prepTime: "5",
      cookTime: "10",
      sourceUrl: "",
      notes: "",
      tags: ["breakfast"],
    });
    expect(s.steps.map((st) => st.text)).toEqual([
      "Whisk the dry ingredients",
      "Fold in the wet",
      "Griddle",
    ]);
    expect(new Set(s.steps.map((st) => st.uid)).size).toBe(3);
  });

  it("a raw_text row seeds a pristine paste draft that re-serializes as its string", () => {
    const s = recipeToState({
      ...sampleRecipe,
      ingredients: [
        {
          id: 9,
          position: 0,
          quantity: 2,
          unit: "tbsp",
          item: "olive oil",
          note: null,
          normalized_name: "olive oil",
          raw_text: "2 tbsp olive oil",
        },
      ],
    });
    expect(s.ingredients[0]).toMatchObject({
      origin: "paste",
      pristine: true,
      raw: "2 tbsp olive oil",
      quantity: "2",
      unit: "tbsp",
      item: "olive oil",
    });
    expect(buildRecipeCreate(s).ingredients).toEqual(["2 tbsp olive oil"]);
  });

  it("a structured row seeds a manual draft (object element on save)", () => {
    const s = recipeToState({
      ...sampleRecipe,
      ingredients: [
        {
          id: 9,
          position: 0,
          quantity: null,
          unit: null,
          item: "salt",
          note: "to taste",
          normalized_name: "salt",
          raw_text: null,
        },
      ],
    });
    expect(s.ingredients[0]).toMatchObject({
      origin: "manual",
      pristine: false,
    });
    expect(buildRecipeCreate(s).ingredients).toEqual([
      { item: "salt", note: "to taste" },
    ]);
  });

  it("an ingredient-less recipe seeds one blank row", () => {
    const s = recipeToState({ ...sampleRecipe, ingredients: [] });
    expect(s.ingredients).toHaveLength(1);
    expect(buildRecipeCreate(s).ingredients).toEqual([]);
  });
});

describe("asOpenableUrl", () => {
  it("accepts http(s) URLs and rejects everything else", () => {
    expect(asOpenableUrl("https://example.com/r")).toBe(
      "https://example.com/r",
    );
    expect(asOpenableUrl("  http://example.com  ")).toBe("http://example.com/");
    expect(asOpenableUrl("ftp://example.com")).toBeNull();
    expect(asOpenableUrl("just a note")).toBeNull();
    expect(asOpenableUrl("")).toBeNull();
  });
});

// ── flow: create vs MSW ──────────────────────────────────────────────────────

describe("RecipeForm create flow", () => {
  it("POSTs the structured draft and redirects to the new recipe", async () => {
    const user = userEvent.setup();
    let posted: unknown;
    server.use(
      http.post("/api/recipes", async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json({ ...sampleRecipe, id: 42 }, { status: 201 });
      }),
    );
    renderForm();

    await user.type(screen.getByLabelText(/^Title/), "Sheet Pan Chicken");
    await user.type(screen.getByLabelText("Prep time (min)"), "15");

    // row 1 is present by default — a fully structured line
    await user.type(screen.getByLabelText("Quantity for ingredient 1"), "2");
    await user.type(screen.getByLabelText("Unit for ingredient 1"), "lb");
    await user.type(
      screen.getByLabelText("Item for ingredient 1"),
      "chicken thighs",
    );
    await user.type(screen.getByLabelText("Note for ingredient 1"), "bone-in");

    // row 2 — blank quantity means "to taste"
    await user.click(screen.getByRole("button", { name: "Add ingredient" }));
    await user.type(
      screen.getByLabelText("Item for ingredient 2"),
      "kosher salt",
    );

    await user.click(screen.getByRole("button", { name: "Add step" }));
    await user.type(screen.getByLabelText("Step 1"), "Heat the oven to 425");

    await user.type(screen.getByLabelText("Add tag"), "dinner{Enter}");

    await user.click(screen.getByRole("button", { name: "Save recipe" }));

    expect(await screen.findByTestId("recipe-landing")).toHaveTextContent(
      "recipe 42",
    );
    expect(posted).toEqual({
      title: "Sheet Pan Chicken",
      notes: "",
      cuisine: null,
      source_url: null,
      prep_time: 15,
      cook_time: null,
      servings: null,
      tags: ["dinner"],
      steps: ["Heat the oven to 425"],
      ingredients: [
        { item: "chicken thighs", quantity: 2, unit: "lb", note: "bone-in" },
        { item: "kosher salt" },
      ],
    });
  });

  it("blocks submit on the client guard when the title is empty", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(
      http.post("/api/recipes", () => {
        called = true;
        return HttpResponse.json(sampleRecipe, { status: 201 });
      }),
    );
    renderForm();

    await user.type(screen.getByLabelText("Item for ingredient 1"), "flour");
    await user.click(screen.getByRole("button", { name: "Save recipe" }));

    expect(await screen.findByText("Title is required.")).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it("maps a 422 loc back to the field and the ingredient row it names", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/recipes", () =>
        HttpResponse.json(
          {
            detail: [
              {
                loc: ["body", "title"],
                msg: "String should have at least 1 character",
                type: "string_too_short",
              },
              {
                loc: ["body", "ingredients", 1, "item"],
                msg: "Field required",
                type: "missing",
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    renderForm();

    await user.type(screen.getByLabelText(/^Title/), "x");
    await user.type(screen.getByLabelText("Item for ingredient 1"), "flour");
    await user.click(screen.getByRole("button", { name: "Add ingredient" }));
    await user.type(screen.getByLabelText("Item for ingredient 2"), "pepper");
    await user.click(screen.getByRole("button", { name: "Save recipe" }));

    expect(
      await screen.findByText("String should have at least 1 character"),
    ).toBeInTheDocument();
    expect(screen.getByText("Field required")).toBeInTheDocument();
    expect(screen.getByLabelText("Item for ingredient 2")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    // row 1 was not the offending row
    expect(screen.getByLabelText("Item for ingredient 1")).not.toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.queryByTestId("recipe-landing")).not.toBeInTheDocument();
  });

  it("renders a string `detail` rejection as a form-level banner", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/recipes", () =>
        HttpResponse.json(
          { detail: "an ingredient row needs item text" },
          { status: 422 },
        ),
      ),
    );
    renderForm();

    await user.type(screen.getByLabelText(/^Title/), "Broth");
    await user.type(screen.getByLabelText("Item for ingredient 1"), "water");
    await user.click(screen.getByRole("button", { name: "Save recipe" }));

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("an ingredient row needs item text");
    expect(screen.queryByTestId("recipe-landing")).not.toBeInTheDocument();
  });

  it("offers an open-link affordance only for a valid URL in source_url", async () => {
    const user = userEvent.setup();
    renderForm();
    const source = screen.getByLabelText("Source URL");

    await user.type(source, "https://example.com/recipe");
    expect(screen.getByRole("link", { name: "Open link" })).toHaveAttribute(
      "href",
      "https://example.com/recipe",
    );

    await user.clear(source);
    await user.type(source, "from grandma");
    expect(
      screen.queryByRole("link", { name: "Open link" }),
    ).not.toBeInTheDocument();
  });
});

// ── flow: paste ingredients with preview (ticket 06b) ─────────────────────────

describe("RecipeForm paste ingredients", () => {
  const PASTE_BLOCK = "- 2 tbsp olive oil\n\nFor the sauce:\n1 onion, diced";

  async function openPaste(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("button", { name: "Paste ingredients" }));
    return screen.getByLabelText("Ingredient lines");
  }

  it("previews per-line parse, dropping the blank line, bullet, and header", async () => {
    const user = userEvent.setup();
    renderForm();

    const textarea = await openPaste(user);
    await user.click(textarea);
    await user.paste(PASTE_BLOCK);

    // header + blank line gone; two rows survive
    expect(screen.queryByText("For the sauce:")).not.toBeInTheDocument();
    const preview = screen.getByRole("table", { name: /Preview/ });
    const bodyRows = within(preview).getAllByRole("row").slice(1); // drop <thead>
    expect(bodyRows).toHaveLength(2);
    expect(within(bodyRows[0]).getByText("olive oil")).toBeInTheDocument();
    expect(within(bodyRows[0]).getByText("tbsp")).toBeInTheDocument();
    expect(within(bodyRows[1]).getByText("onion, diced")).toBeInTheDocument();
  });

  it("cancel discards the preview — no rows appended", async () => {
    const user = userEvent.setup();
    renderForm();

    const textarea = await openPaste(user);
    await user.click(textarea);
    await user.paste(PASTE_BLOCK);
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByLabelText("Item for ingredient 2"),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Item for ingredient 1")).toHaveValue("");
  });

  it("confirm appends parsed rows; untouched → string, edited → object on save", async () => {
    const user = userEvent.setup();
    let posted: { ingredients: unknown } | undefined;
    server.use(
      http.post("/api/recipes", async ({ request }) => {
        posted = (await request.json()) as { ingredients: unknown };
        return HttpResponse.json({ ...sampleRecipe, id: 7 }, { status: 201 });
      }),
    );
    renderForm();

    const textarea = await openPaste(user);
    await user.click(textarea);
    await user.paste(PASTE_BLOCK);
    await user.click(screen.getByRole("button", { name: "Add 2 rows" }));

    // appended after the default blank row 1
    expect(screen.getByLabelText("Item for ingredient 2")).toHaveValue(
      "olive oil",
    );
    expect(screen.getByLabelText("Quantity for ingredient 2")).toHaveValue("2");
    expect(screen.getByLabelText("Item for ingredient 3")).toHaveValue(
      "onion, diced",
    );

    // hand-fix the second appended row → it must serialize as an object
    await user.type(
      screen.getByLabelText("Item for ingredient 3"),
      " and garlic",
    );

    await user.type(screen.getByLabelText(/^Title/), "Pan sauce");
    await user.click(screen.getByRole("button", { name: "Save recipe" }));

    expect(await screen.findByTestId("recipe-landing")).toHaveTextContent(
      "recipe 7",
    );
    expect(posted?.ingredients).toEqual([
      "2 tbsp olive oil",
      { item: "onion, diced and garlic", quantity: 1 },
    ]);
  });
});

// ── flow: edit / PUT full-replace vs MSW (ticket 06c) ─────────────────────────

describe("RecipeForm edit flow", () => {
  const pastedRow: RecipeIngredientRead = {
    id: 20,
    position: 0,
    quantity: 2,
    unit: "tbsp",
    item: "olive oil",
    note: null,
    normalized_name: "olive oil",
    raw_text: "2 tbsp olive oil",
  };
  const structuredRow: RecipeIngredientRead = {
    id: 21,
    position: 1,
    quantity: 1,
    unit: null,
    item: "onion",
    note: "diced",
    normalized_name: "onion",
    raw_text: null,
  };
  const editable: RecipeRead = {
    ...sampleRecipe,
    id: 3,
    title: "Pan Sauce",
    steps: ["Sweat aromatics", "Deglaze"],
    ingredients: [pastedRow, structuredRow],
  };

  /** Emulate the server PUT full-replace: rebuild the read rows from the sent
   *  elements, re-parsing a bare string the way the backend would. */
  function applyReplace(prev: RecipeRead, body: RecipeUpdate): RecipeRead {
    return {
      ...prev,
      ...body,
      updated_at: "2026-09-02T12:00:00+00:00",
      ingredients: body.ingredients.map((el, i) => {
        if (typeof el === "string") {
          const p = parseIngredientLine(el);
          return {
            id: 100 + i,
            position: i,
            quantity: p.quantity,
            unit: p.unit ?? null,
            item: p.item,
            note: p.note ?? null,
            normalized_name: p.item,
            raw_text: el,
          };
        }
        return {
          id: 100 + i,
          position: i,
          quantity: el.quantity ?? null,
          unit: el.unit ?? null,
          item: el.item ?? "",
          note: el.note ?? null,
          normalized_name: el.item ?? "",
          raw_text: null,
        };
      }),
    };
  }

  function RecipeLandingWithEdit() {
    const { id } = useParams();
    return (
      <>
        <p data-testid="recipe-landing">recipe {id}</p>
        <Link to={`/recipes/${id}/edit`}>Re-edit</Link>
      </>
    );
  }

  function renderEdit() {
    const queryClient = makeQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/recipes/3/edit"]}>
          <ToastProvider>
            <Routes>
              <Route
                path="/recipes/:id/edit"
                element={<RecipeForm mode="edit" />}
              />
              <Route path="/recipes/:id" element={<RecipeLandingWithEdit />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    return queryClient;
  }

  it("fetches the recipe and pre-fills every field, step, and ingredient row", async () => {
    server.use(http.get("/api/recipes/:id", () => HttpResponse.json(editable)));
    renderEdit();

    expect(await screen.findByLabelText(/^Title/)).toHaveValue("Pan Sauce");
    expect(screen.getByLabelText("Prep time (min)")).toHaveValue(5);
    expect(screen.getByLabelText("Step 1")).toHaveValue("Sweat aromatics");
    expect(screen.getByLabelText("Step 2")).toHaveValue("Deglaze");
    expect(screen.getByLabelText("Item for ingredient 1")).toHaveValue(
      "olive oil",
    );
    expect(screen.getByLabelText("Quantity for ingredient 1")).toHaveValue("2");
    expect(screen.getByLabelText("Unit for ingredient 1")).toHaveValue("tbsp");
    expect(screen.getByLabelText("Item for ingredient 2")).toHaveValue("onion");
    expect(screen.getByLabelText("Note for ingredient 2")).toHaveValue("diced");
  });

  it("PUT full-replace drops removed rows / steps; refetch shows them gone with no stale-key crash", async () => {
    const user = userEvent.setup();
    let current = editable;
    const puts: RecipeUpdate[] = [];
    server.use(
      http.get("/api/recipes/:id", () => HttpResponse.json(current)),
      http.put("/api/recipes/:id", async ({ request }) => {
        const body = (await request.json()) as RecipeUpdate;
        puts.push(body);
        current = applyReplace(current, body);
        return HttpResponse.json(current);
      }),
    );
    renderEdit();

    await screen.findByLabelText(/^Title/);
    await user.click(
      screen.getByRole("button", { name: "Remove ingredient 2" }),
    );
    await user.click(screen.getByRole("button", { name: "Remove step 2" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByTestId("recipe-landing")).toHaveTextContent(
      "recipe 3",
    );
    expect(puts).toHaveLength(1);
    expect(puts[0]).toMatchObject({
      title: "Pan Sauce",
      steps: ["Sweat aromatics"],
      // untouched pasted row stays a string; the structured onion row is gone
      ingredients: ["2 tbsp olive oil"],
    });

    // re-open the same recipe: the refetch reflects the replace, keys are fresh
    await user.click(screen.getByRole("link", { name: "Re-edit" }));
    expect(await screen.findByLabelText(/^Title/)).toHaveValue("Pan Sauce");
    expect(screen.getByLabelText("Step 1")).toHaveValue("Sweat aromatics");
    expect(screen.queryByLabelText("Step 2")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Item for ingredient 1")).toHaveValue(
      "olive oil",
    );
    expect(
      screen.queryByLabelText("Item for ingredient 2"),
    ).not.toBeInTheDocument();
  });

  it("on edit an untouched pasted row stays a string; an edited one becomes an object", async () => {
    const user = userEvent.setup();
    let put: RecipeUpdate | undefined;
    server.use(
      http.get("/api/recipes/:id", () => HttpResponse.json(editable)),
      http.put("/api/recipes/:id", async ({ request }) => {
        put = (await request.json()) as RecipeUpdate;
        return HttpResponse.json(editable);
      }),
    );
    renderEdit();

    await screen.findByLabelText(/^Title/);
    // edit the pasted row → it must serialize as an object, not the raw string
    await user.type(
      screen.getByLabelText("Item for ingredient 1"),
      " (extra virgin)",
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await screen.findByTestId("recipe-landing");
    expect(put?.ingredients).toEqual([
      { item: "olive oil (extra virgin)", quantity: 2, unit: "tbsp" },
      { item: "onion", quantity: 1, note: "diced" },
    ]);
  });

  it("shows a not-found panel when the recipe 404s", async () => {
    server.use(
      http.get("/api/recipes/:id", () =>
        HttpResponse.json({ detail: "Recipe not found" }, { status: 404 }),
      ),
    );
    renderEdit();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /doesn.t exist/i,
    );
    expect(screen.getByRole("link", { name: /recipes/i })).toHaveAttribute(
      "href",
      "/",
    );
  });
});
