import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { sampleGroceryItem, sampleGroceryList } from "../test/handlers";
import { GENERIC_ERROR_MESSAGE, STOCK_CONFLICT_MESSAGE } from "../lib/apiError";
import type { GroceryListItemRead, GroceryListRead } from "../types";
import { ToastProvider } from "../components";
import GroceryListDetail from "./GroceryListDetail";

function makeList(items: GroceryListItemRead[]): GroceryListRead {
  return { ...sampleGroceryList, items };
}

function useGroceryList(list: GroceryListRead) {
  server.use(http.get("/api/grocery/:id", () => HttpResponse.json(list)));
}

function renderPage(path = "/groceries/1") {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/groceries/:id" element={<GroceryListDetail />} />
            <Route path="/groceries" element={<h1>Grocery lists</h1>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

describe("GroceryListDetail", () => {
  it("renders lines grouped by source with formatted quantities", async () => {
    useGroceryList(
      makeList([
        { ...sampleGroceryItem, id: 1, item: "flour", source: "generated" },
        {
          ...sampleGroceryItem,
          id: 2,
          item: "duct tape",
          source: "manual",
          quantity: 1,
          unit: "unit",
        },
      ]),
    );
    renderPage();

    expect(await screen.findByText("From your recipes")).toBeInTheDocument();
    expect(screen.getByText("Added manually")).toBeInTheDocument();
    expect(screen.getByText("flour")).toBeInTheDocument();
    expect(screen.getByText("250 g")).toBeInTheDocument();
    expect(screen.getByText("duct tape")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("omits an empty group", async () => {
    useGroceryList(
      makeList([{ ...sampleGroceryItem, id: 1, source: "generated" }]),
    );
    renderPage();

    expect(await screen.findByText("From your recipes")).toBeInTheDocument();
    expect(screen.queryByText("Added manually")).not.toBeInTheDocument();
  });

  it("shows a nettable:false line as 'amount uncertain' with no number", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "canned beans",
          nettable: false,
          quantity: 100,
          unit: "g",
        },
      ]),
    );
    renderPage();

    expect(await screen.findByText("canned beans")).toBeInTheDocument();
    expect(screen.getByText("amount uncertain")).toBeInTheDocument();
    expect(
      screen.getByText("buy based on what you find you’re short."),
    ).toBeInTheDocument();
    expect(screen.queryByText("100 g")).not.toBeInTheDocument();
  });

  it("shows the empty state when the list has no items", async () => {
    useGroceryList(makeList([]));
    renderPage();
    expect(
      await screen.findByText("No items on this list yet."),
    ).toBeInTheDocument();
  });

  it("tapping a line checks it off immediately, and a 409 rolls it back", async () => {
    useGroceryList(
      makeList([
        { ...sampleGroceryItem, id: 1, item: "flour", checked: false },
      ]),
    );
    let resolvePatch!: () => void;
    server.use(
      http.patch(
        "/api/grocery/:id/items/:itemId",
        () =>
          new Promise((resolve) => {
            resolvePatch = () =>
              resolve(
                HttpResponse.json({ detail: "conflict" }, { status: 409 }),
              );
          }),
      ),
    );
    renderPage();

    const checkbox = await screen.findByRole("checkbox", { name: "flour" });
    expect(checkbox).not.toBeChecked();

    await userEvent.click(checkbox);
    expect(checkbox).toBeChecked(); // instant — before the response resolves

    resolvePatch();
    await waitFor(() => expect(checkbox).not.toBeChecked());
    expect(await screen.findByText(GENERIC_ERROR_MESSAGE)).toBeInTheDocument();
  });

  it("tapping a line checks it off and keeps it checked on success", async () => {
    useGroceryList(
      makeList([
        { ...sampleGroceryItem, id: 1, item: "flour", checked: false },
      ]),
    );
    server.use(
      http.patch("/api/grocery/:id/items/:itemId", () => {
        // Success invalidates the query — point the follow-up refetch at the
        // now-checked line so a real server round trip wouldn't flip it back.
        useGroceryList(
          makeList([
            { ...sampleGroceryItem, id: 1, item: "flour", checked: true },
          ]),
        );
        return HttpResponse.json({ ...sampleGroceryItem, checked: true });
      }),
    );
    renderPage();

    const checkbox = await screen.findByRole("checkbox", { name: "flour" });
    await userEvent.click(checkbox);

    expect(checkbox).toBeChecked();
    await waitFor(() => expect(checkbox).toBeChecked());
  });

  it("does not allow toggling a frozen (added_to_inventory) line", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          added_to_inventory: true,
          applied_quantity: 250,
          applied_unit: "g",
        },
      ]),
    );
    renderPage();

    const checkbox = await screen.findByRole("checkbox", { name: "flour" });
    expect(checkbox).toBeDisabled();
    expect(screen.getByText("Added to inventory")).toBeInTheDocument();
  });

  it("disables every checkbox on an archived list", async () => {
    useGroceryList({
      ...sampleGroceryList,
      status: "archived",
      items: [{ ...sampleGroceryItem, id: 1, item: "flour" }],
    });
    renderPage();

    expect(await screen.findByText("Archived")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "flour" })).toBeDisabled();
  });

  it("shows a not-found panel for a 404", async () => {
    server.use(
      http.get("/api/grocery/:id", () =>
        HttpResponse.json({ detail: "Not Found" }, { status: 404 }),
      ),
    );
    renderPage();

    expect(
      await screen.findByText("Grocery list not found"),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("link", { name: "Back to grocery lists" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Grocery lists" }),
    ).toBeInTheDocument();
  });

  it("surfaces a query failure with a retry affordance", async () => {
    useGroceryList(makeList([{ ...sampleGroceryItem, id: 1 }]));
    server.use(
      http.get("/api/grocery/:id", () =>
        HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 }),
      ),
    );
    renderPage();
    const panel = await screen.findByRole("alert");
    expect(panel).toHaveTextContent("Internal Server Error");
  });

  it("adds a manual line, POSTing the right body, and it appears in the manual group", async () => {
    useGroceryList(makeList([{ ...sampleGroceryItem, id: 1, item: "flour" }]));
    let postedBody: unknown;
    server.use(
      http.post("/api/grocery/:id/items", async ({ request }) => {
        postedBody = await request.json();
        const created: GroceryListItemRead = {
          ...sampleGroceryItem,
          id: 2,
          item: "duct tape",
          source: "manual",
          quantity: 2,
          unit: "roll",
        };
        useGroceryList(
          makeList([{ ...sampleGroceryItem, id: 1, item: "flour" }, created]),
        );
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderPage();
    await screen.findByText("flour");

    await userEvent.type(screen.getByLabelText("Item"), "duct tape");
    await userEvent.type(screen.getByLabelText("Quantity"), "2");
    await userEvent.type(screen.getByLabelText("Unit"), "roll");
    await userEvent.click(screen.getByRole("button", { name: "Add item" }));

    await waitFor(() =>
      expect(postedBody).toEqual({
        item: "duct tape",
        quantity: 2,
        unit: "roll",
      }),
    );
    expect(await screen.findByText("Added manually")).toBeInTheDocument();
    expect(screen.getByText("duct tape")).toBeInTheDocument();
  });

  it("adds a manual line with no quantity/unit, sending both keys as null", async () => {
    useGroceryList(makeList([{ ...sampleGroceryItem, id: 1, item: "flour" }]));
    let postedBody: unknown;
    server.use(
      http.post("/api/grocery/:id/items", async ({ request }) => {
        postedBody = await request.json();
        return HttpResponse.json(
          { ...sampleGroceryItem, id: 2, item: "napkins", source: "manual" },
          { status: 201 },
        );
      }),
    );
    renderPage();
    await screen.findByText("flour");

    await userEvent.type(screen.getByLabelText("Item"), "napkins");
    await userEvent.click(screen.getByRole("button", { name: "Add item" }));

    // Both keys must be present (possibly null) — the backend schema has no
    // default for them, so omitting either 422s (ticket 18 re-diff).
    await waitFor(() =>
      expect(postedBody).toEqual({ item: "napkins", quantity: null, unit: null }),
    );
  });

  it("edits a generated line's quantity, sending quantity+unit together, and shows the reclassify note", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          source: "generated",
          quantity: 250,
          unit: "g",
        },
      ]),
    );
    let patchedBody: unknown;
    server.use(
      http.patch("/api/grocery/:id/items/:itemId", async ({ request }) => {
        patchedBody = await request.json();
        const updated: GroceryListItemRead = {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          source: "manual",
          nettable: true,
          quantity: 500,
          unit: "g",
        };
        useGroceryList(makeList([updated]));
        return HttpResponse.json(updated);
      }),
    );
    renderPage();
    await screen.findByText("flour");

    await userEvent.click(screen.getByRole("button", { name: "Edit flour" }));
    const editForm = screen.getByRole("form", { name: "Edit flour" });
    const quantityField = within(editForm).getByLabelText("Quantity");
    await userEvent.clear(quantityField);
    await userEvent.type(quantityField, "500");
    await userEvent.click(
      within(editForm).getByRole("button", { name: "Save" }),
    );

    await waitFor(() =>
      expect(patchedBody).toEqual({ quantity: 500, unit: "g" }),
    );
    expect(
      await screen.findByText(
        "This is now a manual line — we'll stop netting it against your stock.",
      ),
    ).toBeInTheDocument();
  });

  it("does not show an edit affordance on a frozen line", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          added_to_inventory: true,
        },
      ]),
    );
    renderPage();
    await screen.findByText("flour");
    expect(
      screen.queryByRole("button", { name: "Edit flour" }),
    ).not.toBeInTheDocument();
  });

  it("does not show an edit affordance on an archived list", async () => {
    useGroceryList({
      ...sampleGroceryList,
      status: "archived",
      items: [{ ...sampleGroceryItem, id: 1, item: "flour" }],
    });
    renderPage();
    expect(await screen.findByText("Archived")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit flour" }),
    ).not.toBeInTheDocument();
  });

  it("shows a frozen line as read-only with the applied amount, not the original quantity", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          quantity: 250,
          unit: "g",
          added_to_inventory: true,
          applied_quantity: 500,
          applied_unit: "g",
        },
      ]),
    );
    renderPage();

    expect(await screen.findByText("Added to inventory")).toBeInTheDocument();
    expect(screen.getByText("500 g")).toBeInTheDocument();
    expect(screen.queryByText("250 g")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit flour" }),
    ).not.toBeInTheDocument();
  });

  it("opens a submit dialog explaining the change; confirming submits, freezes the line, and invalidates inventory", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          checked: true,
          quantity: 250,
          unit: "g",
        },
      ]),
    );
    let submitted = false;
    server.use(
      http.post("/api/grocery/:id/submit", () => {
        submitted = true;
        useGroceryList(
          makeList([
            {
              ...sampleGroceryItem,
              id: 1,
              item: "flour",
              checked: true,
              quantity: 250,
              unit: "g",
              added_to_inventory: true,
              applied_quantity: 250,
              applied_unit: "g",
            },
          ]),
        );
        return HttpResponse.json(sampleGroceryList);
      }),
    );
    const queryClient = renderPage();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByText("flour");

    await userEvent.click(
      screen.getByRole("button", { name: "Submit checked items to inventory" }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Add checked items to inventory?",
    });
    expect(within(dialog).getByText(/can’t be undone/)).toBeInTheDocument();

    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add to inventory" }),
    );

    await waitFor(() => expect(submitted).toBe(true));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(await screen.findByText("Added to inventory")).toBeInTheDocument();
    const keys = invalidate.mock.calls.map(
      (c) => (c[0] as { queryKey?: unknown[] } | undefined)?.queryKey,
    );
    expect(keys).toContainEqual(["grocery", 1]);
    expect(keys).toContainEqual(["inventory"]);
  });

  it("canceling the submit dialog does not submit", async () => {
    useGroceryList(
      makeList([{ ...sampleGroceryItem, id: 1, item: "flour", checked: true }]),
    );
    let submitted = false;
    server.use(
      http.post("/api/grocery/:id/submit", () => {
        submitted = true;
        return HttpResponse.json(sampleGroceryList);
      }),
    );
    renderPage();
    await screen.findByText("flour");

    await userEvent.click(
      screen.getByRole("button", { name: "Submit checked items to inventory" }),
    );
    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(submitted).toBe(false);
  });

  // §6 catalog: 409 "conflict" (IntegrityError / lock timeout) on `submit` →
  // toast + refetch, same generic-conflict surface as the cook/inventory rows.
  it("on a 409 stock collision from submit, toasts a retry message and refetches", async () => {
    useGroceryList(
      makeList([{ ...sampleGroceryItem, id: 1, item: "flour", checked: true }]),
    );
    server.use(errorHandlers.conflict("post", "/api/grocery/:id/submit"));
    const queryClient = renderPage();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByText("flour");

    await userEvent.click(
      screen.getByRole("button", { name: "Submit checked items to inventory" }),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add to inventory" }),
    );

    expect(await screen.findByText(STOCK_CONFLICT_MESSAGE)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    const keys = invalidate.mock.calls.map(
      (c) => (c[0] as { queryKey?: unknown[] } | undefined)?.queryKey,
    );
    expect(keys).toContainEqual(["grocery", 1]);
  });

  it("re-running submit after checking more is allowed — the button stays available", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          checked: true,
          added_to_inventory: true,
          applied_quantity: 250,
          applied_unit: "g",
        },
      ]),
    );
    renderPage();
    await screen.findByText("Added to inventory");

    expect(
      screen.getByRole("button", { name: "Submit checked items to inventory" }),
    ).toBeEnabled();
  });

  it("a stale edit that races a freeze closes the editor with the frozen-line message", async () => {
    useGroceryList(
      makeList([
        {
          ...sampleGroceryItem,
          id: 1,
          item: "flour",
          source: "generated",
          quantity: 250,
          unit: "g",
        },
      ]),
    );
    server.use(
      errorHandlers.frozenLine("patch", "/api/grocery/:id/items/:itemId"),
    );
    renderPage();
    await screen.findByText("flour");

    await userEvent.click(screen.getByRole("button", { name: "Edit flour" }));
    const editForm = screen.getByRole("form", { name: "Edit flour" });
    const quantityField = within(editForm).getByLabelText("Quantity");
    await userEvent.clear(quantityField);
    await userEvent.type(quantityField, "500");
    await userEvent.click(
      within(editForm).getByRole("button", { name: "Save" }),
    );

    expect(
      await screen.findByText("This item was already added to inventory."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: "Edit flour" }),
    ).not.toBeInTheDocument();
  });

  it("a stale edit on an archived list closes the editor with the archived-list message", async () => {
    useGroceryList(makeList([{ ...sampleGroceryItem, id: 1, item: "flour" }]));
    server.use(
      errorHandlers.listNotActive("patch", "/api/grocery/:id/items/:itemId"),
    );
    renderPage();
    await screen.findByText("flour");

    await userEvent.click(screen.getByRole("button", { name: "Edit flour" }));
    const editForm = screen.getByRole("form", { name: "Edit flour" });
    await userEvent.click(within(editForm).getByLabelText("Item"));
    await userEvent.type(within(editForm).getByLabelText("Item"), "!");
    await userEvent.click(
      within(editForm).getByRole("button", { name: "Save" }),
    );

    expect(
      await screen.findByText("This list is archived."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: "Edit flour" }),
    ).not.toBeInTheDocument();
  });

  it("opens an archive dialog; confirming archives the list", async () => {
    useGroceryList(makeList([{ ...sampleGroceryItem, id: 1, item: "flour" }]));
    server.use(
      http.post("/api/grocery/:id/archive", () => {
        useGroceryList({
          ...makeList([{ ...sampleGroceryItem, id: 1, item: "flour" }]),
          status: "archived",
        });
        return HttpResponse.json({ ...sampleGroceryList, status: "archived" });
      }),
    );
    renderPage();
    await screen.findByText("flour");

    await userEvent.click(screen.getByRole("button", { name: "Archive list" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Archive this list?",
    });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Archive" }),
    );

    expect(await screen.findByText("Archived")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Archive list" }),
    ).not.toBeInTheDocument();
  });

  it("a 409 on archive (archived by someone else) shows a refetch message", async () => {
    useGroceryList(makeList([{ ...sampleGroceryItem, id: 1, item: "flour" }]));
    server.use(errorHandlers.listNotActive("post", "/api/grocery/:id/archive"));
    renderPage();
    await screen.findByText("flour");

    await userEvent.click(screen.getByRole("button", { name: "Archive list" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Archive this list?",
    });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Archive" }),
    );

    expect(
      await screen.findByText("This list is archived."),
    ).toBeInTheDocument();
  });
});
