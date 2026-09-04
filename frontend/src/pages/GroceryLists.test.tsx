import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { sampleGroceryItem, sampleGroceryList } from "../test/handlers";
import type { GroceryListRead } from "../types";
import { ToastProvider } from "../components";
import GroceryLists from "./GroceryLists";

function makeList(over: Partial<GroceryListRead>): GroceryListRead {
  return { ...sampleGroceryList, ...over };
}

const activeList = makeList({
  id: 1,
  name: "Weekly shop",
  status: "active",
  items: [
    sampleGroceryItem,
    { ...sampleGroceryItem, id: 2, item: "eggs", checked: true },
    { ...sampleGroceryItem, id: 3, item: "milk", checked: true },
  ],
});
const archivedList = makeList({
  id: 2,
  name: "Last month",
  status: "archived",
  items: [{ ...sampleGroceryItem, id: 4, checked: true }],
});

/** Serves different lists per `?status=` — also lets tests assert which
 *  status the request actually carried. */
function useGroceryLists(byStatus: Partial<Record<string, GroceryListRead[]>>) {
  server.use(
    http.get("/api/grocery", ({ request }) => {
      const status = new URL(request.url).searchParams.get("status");
      return HttpResponse.json((status && byStatus[status]) ?? []);
    }),
  );
}

function renderPage(path = "/groceries") {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/groceries" element={<GroceryLists />} />
            <Route
              path="/groceries/:id"
              element={<h1>Grocery list detail</h1>}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

describe("GroceryLists", () => {
  it("defaults to active and shows item/checked counts", async () => {
    useGroceryLists({ active: [activeList], archived: [archivedList] });
    renderPage();

    expect(await screen.findByText("Weekly shop")).toBeInTheDocument();
    expect(screen.queryByText("Last month")).not.toBeInTheDocument();
    expect(screen.getByText("2 of 3 items checked")).toBeInTheDocument();
  });

  it("switching to archived re-queries with ?status=archived", async () => {
    useGroceryLists({ active: [activeList], archived: [archivedList] });
    renderPage();
    await screen.findByText("Weekly shop");

    await userEvent.click(screen.getByRole("button", { name: "Archived" }));

    expect(await screen.findByText("Last month")).toBeInTheDocument();
    expect(screen.queryByText("Weekly shop")).not.toBeInTheDocument();
    expect(screen.getByText("1 of 1 item checked")).toBeInTheDocument();
  });

  it("opens a list", async () => {
    useGroceryLists({ active: [activeList] });
    renderPage();
    await userEvent.click(
      await screen.findByRole("link", { name: "Weekly shop" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Grocery list detail" }),
    ).toBeInTheDocument();
  });

  it("shows the empty state for the current filter", async () => {
    useGroceryLists({ active: [], archived: [archivedList] });
    renderPage();
    expect(
      await screen.findByText("No active grocery lists."),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Archived" }));
    expect(await screen.findByText("Last month")).toBeInTheDocument();
  });

  it("deletes a list after confirming", async () => {
    useGroceryLists({ active: [activeList] });
    server.use(
      http.delete(
        "/api/grocery/:id",
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    renderPage();
    await screen.findByText("Weekly shop");

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    const dialog = await screen.findByRole("dialog", {
      name: "Delete grocery list?",
    });
    expect(within(dialog).getByText(/Weekly shop/)).toBeInTheDocument();

    // switch the list backing the query so the post-delete refetch reflects
    // the deletion, then confirm.
    useGroceryLists({ active: [] });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Delete" }),
    );

    expect(
      await screen.findByText("No active grocery lists."),
    ).toBeInTheDocument();
  });

  it("cancelling the delete dialog keeps the list", async () => {
    useGroceryLists({ active: [activeList] });
    renderPage();
    await screen.findByText("Weekly shop");

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Delete grocery list?",
    });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Cancel" }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("Weekly shop")).toBeInTheDocument();
  });

  it("surfaces a query failure with a retry affordance", async () => {
    server.use(errorHandlers.serverError("get", "/api/grocery"));
    renderPage();
    const panel = await screen.findByRole("alert");
    expect(
      within(panel).getByRole("button", { name: "Retry" }),
    ).toBeInTheDocument();
  });
});
