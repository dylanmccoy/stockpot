import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { server } from "../test/server";
import { makeQueryClient } from "../test/helpers";
import { sampleRecipe } from "../test/handlers";
import { ToastProvider } from "../components";
import RecipeForm, {
  asOpenableUrl,
  buildRecipeCreate,
  ingredientRowsToSubmit,
  type RecipeFormState,
} from "./RecipeForm";

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
      {
        uid: "r1",
        quantity: "2",
        unit: "lb",
        item: "chicken thighs",
        note: "bone-in",
      },
      { uid: "r2", quantity: "", unit: "", item: "kosher salt", note: "" },
      { uid: "r3", quantity: "", unit: "", item: "", note: "" },
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
