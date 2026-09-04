import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { makeCookLog, makeDeduction as ded } from "../test/handlers";
import type { CookLogRead } from "../types";
import History from "./History";

const AT = "2026-09-01T12:00:00+00:00";

/** `n` cook logs, ids `n..1`, already newest-first (server order). */
function feed(
  n: number,
  over: (i: number) => Partial<CookLogRead> = () => ({}),
) {
  return Array.from({ length: n }, (_, i) => {
    const id = n - i;
    return makeCookLog({
      id,
      recipe_id: id,
      recipe_title: `Recipe ${id}`,
      cooked_at: AT,
      cooked_by: { id: 1, username: "sam" },
      ...over(id),
    });
  });
}

/** Offset-aware `/api/cook-logs` backed by `all`. */
function useCookLogs(all: CookLogRead[]) {
  server.use(
    http.get("/api/cook-logs", ({ request }) => {
      const url = new URL(request.url);
      const limit = Number(url.searchParams.get("limit") ?? 50);
      const offset = Number(url.searchParams.get("offset") ?? 0);
      return HttpResponse.json({
        items: all.slice(offset, offset + limit),
        total: all.length,
        limit,
        offset,
      });
    }),
  );
}

function renderHistory() {
  render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={["/history"]}>
        <Routes>
          <Route path="/history" element={<History />} />
          <Route path="/recipes/:id" element={<h1>Recipe detail</h1>} />
          <Route path="/" element={<h1>Recipes</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("History — global feed", () => {
  it("renders the first page with the total count", async () => {
    useCookLogs(feed(55));
    renderHistory();

    expect(await screen.findByText("Showing 50 of 55")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(50);
    // newest first: id 55 before id 6
    const titles = screen.getAllByRole("link").map((a) => a.textContent);
    expect(titles[0]).toBe("Recipe 55");
    expect(titles[49]).toBe("Recipe 6");
  });

  it("names each row's recipe and links to it", async () => {
    useCookLogs(feed(2));
    renderHistory();

    const link = await screen.findByRole("link", { name: "Recipe 2" });
    expect(link).toHaveAttribute("href", "/recipes/2");
  });

  it("'load more' advances the offset and appends the next page", async () => {
    const user = userEvent.setup();
    useCookLogs(feed(55));
    renderHistory();

    await screen.findByText("Showing 50 of 55");
    await user.click(screen.getByRole("button", { name: "Load more" }));

    expect(await screen.findByText("Showing 55 of 55")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(55);
    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a since-deleted recipe's title as plain text with no link", async () => {
    useCookLogs([
      makeCookLog({
        id: 1,
        recipe_id: null,
        recipe_title: "Ghost Stew",
        cooked_at: AT,
        cooked_by: { id: 1, username: "sam" },
      }),
    ]);
    renderHistory();

    expect(await screen.findByText("Ghost Stew")).toBeInTheDocument();
    expect(screen.getByText(/recipe deleted/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Ghost Stew/ }),
    ).not.toBeInTheDocument();
  });

  it("expands a row to its per-ingredient deduction detail", async () => {
    const user = userEvent.setup();
    useCookLogs([
      makeCookLog({
        id: 1,
        recipe_id: 1,
        recipe_title: "Recipe 1",
        deducted: true,
        cooked_at: AT,
        cooked_by: { id: 1, username: "sam" },
        deductions: [ded("ok", "flour"), ded("clamped to 0", "butter")],
      }),
    ]);
    renderHistory();

    await user.click(
      await screen.findByRole("button", { name: /2 ingredients/ }),
    );
    const table = screen.getByRole("table");
    expect(within(table).getByText("ran out")).toBeInTheDocument();
  });

  it("shows an empty state when nothing has been cooked", async () => {
    useCookLogs([]);
    renderHistory();

    expect(await screen.findByText("No cooks logged yet.")).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });

  it("shows an inline retry panel when the first page fails", async () => {
    server.use(errorHandlers.serverError("get", "/api/cook-logs"));
    renderHistory();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
