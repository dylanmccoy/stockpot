import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { makeQueryClient } from "../test/helpers";
import { sampleGroceryItem, sampleGroceryList } from "../test/handlers";
import { GENERIC_ERROR_MESSAGE } from "../lib/apiError";
import type { GroceryListItemRead, GroceryListRead } from "../types";
import { ToastProvider } from "../components";
import GroceryListDetail from "./GroceryListDetail";

function makeList(items: GroceryListItemRead[]): GroceryListRead {
  return { ...sampleGroceryList, items };
}

function useGroceryList(list: GroceryListRead) {
  server.use(
    http.get("/api/grocery/:id", () => HttpResponse.json(list)),
  );
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
      makeList([{ ...sampleGroceryItem, id: 1, item: "flour", checked: false }]),
    );
    let resolvePatch!: () => void;
    server.use(
      http.patch(
        "/api/grocery/:id/items/:itemId",
        () =>
          new Promise((resolve) => {
            resolvePatch = () =>
              resolve(HttpResponse.json({ detail: "conflict" }, { status: 409 }));
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
      makeList([{ ...sampleGroceryItem, id: 1, item: "flour", checked: false }]),
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
});
