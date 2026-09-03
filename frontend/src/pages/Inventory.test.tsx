import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { makeQueryClient } from "../test/helpers";
import { sampleInventoryItem } from "../test/handlers";
import { ToastProvider } from "../components";
import type { InventoryItemRead } from "../types";
import Inventory, {
  buildInventoryCreate,
  emptyAddDraft,
  sortInventory,
  stockLabel,
  validateAddDraft,
} from "./Inventory";

const mk = (over: Partial<InventoryItemRead>): InventoryItemRead => ({
  ...sampleInventoryItem,
  ...over,
});

function renderInventory() {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <Inventory />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

// ── pure: the draft → POST-body seam ─────────────────────────────────────────

describe("buildInventoryCreate", () => {
  it("trims scalars and coerces the quantity", () => {
    expect(
      buildInventoryCreate({
        item: "  Olive oil  ",
        quantity: " 500 ",
        unit: "ml",
        matchName: "Olive Oil",
      }),
    ).toEqual({
      item: "Olive oil",
      quantity: 500,
      unit: "ml",
      match_name: "Olive Oil",
    });
  });

  it("omits a blank unit and a blank match name", () => {
    expect(
      buildInventoryCreate({
        item: "Eggs",
        quantity: "12",
        unit: "   ",
        matchName: "   ",
      }),
    ).toEqual({ item: "Eggs", quantity: 12 });
  });
});

describe("validateAddDraft", () => {
  it("flags a blank item and a missing quantity", () => {
    expect(validateAddDraft(emptyAddDraft())).toEqual({
      item: "Enter an item name.",
      quantity: "Enter a quantity of zero or more.",
    });
  });

  it("rejects a negative quantity but accepts zero", () => {
    expect(
      validateAddDraft({
        item: "Flour",
        quantity: "-1",
        unit: "",
        matchName: "",
      }),
    ).toEqual({ quantity: "Enter a quantity of zero or more." });
    expect(
      validateAddDraft({
        item: "Flour",
        quantity: "0",
        unit: "",
        matchName: "",
      }),
    ).toBeNull();
  });
});

describe("sortInventory", () => {
  it("orders by match name, then unit bucket, case-insensitively", () => {
    const sorted = sortInventory([
      mk({ id: 1, match_name: "sugar", unit_bucket: "mass" }),
      mk({ id: 2, match_name: "Butter", unit_bucket: "mass" }),
      mk({ id: 3, match_name: "butter", unit_bucket: "count" }),
    ]);
    expect(sorted.map((i) => i.id)).toEqual([3, 2, 1]);
  });
});

describe("stockLabel", () => {
  it("snaps the number and trails the display unit", () => {
    expect(stockLabel(mk({ display_quantity: 1000, display_unit: "g" }))).toBe(
      "1000 g",
    );
  });

  it("renders a COUNT row (null unit) as the bare count", () => {
    expect(stockLabel(mk({ display_quantity: 3, display_unit: null }))).toBe(
      "3",
    );
  });
});

// ── flow: table + add + delete vs MSW ───────────────────────────────────────

describe("Inventory screen", () => {
  it("renders the stock table from the ['inventory'] query", async () => {
    server.use(
      http.get("/api/inventory", () =>
        HttpResponse.json([
          mk({
            id: 1,
            item: "Flour",
            match_name: "flour",
            unit_bucket: "mass",
          }),
        ]),
      ),
    );
    renderInventory();

    const table = await screen.findByRole("table");
    const row = within(table).getByText("Flour").closest("tr")!;
    expect(within(row).getByText("flour")).toBeInTheDocument();
    expect(within(row).getByText("mass")).toBeInTheDocument();
    expect(within(row).getByText("1000 g")).toBeInTheDocument();
  });

  it("POSTs the built body and shows the new row after refetch", async () => {
    const user = userEvent.setup();
    let items: InventoryItemRead[] = [];
    let posted: unknown;
    server.use(
      http.get("/api/inventory", () => HttpResponse.json(items)),
      http.post("/api/inventory", async ({ request }) => {
        posted = await request.json();
        const created = mk({
          id: 99,
          item: "Olive oil",
          match_name: "olive oil",
          unit_bucket: "volume",
          display_unit: "ml",
          display_quantity: 500,
        });
        items = [...items, created];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderInventory();

    // starts on the empty state
    expect(
      await screen.findByText("No stock yet — add an item above."),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText(/^Item/), "Olive oil");
    await user.type(screen.getByLabelText(/^Quantity/), "500");
    await user.type(screen.getByLabelText("Unit"), "ml");
    await user.type(screen.getByLabelText("Match name"), "Olive Oil");
    await user.click(screen.getByRole("button", { name: "Add stock" }));

    expect(await screen.findByText("Olive oil")).toBeInTheDocument();
    expect(posted).toEqual({
      item: "Olive oil",
      quantity: 500,
      unit: "ml",
      match_name: "Olive Oil",
    });
  });

  it("blocks the POST on the client guard when the item is blank", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(
      http.get("/api/inventory", () => HttpResponse.json([])),
      http.post("/api/inventory", () => {
        called = true;
        return HttpResponse.json(sampleInventoryItem, { status: 201 });
      }),
    );
    renderInventory();

    await user.type(screen.getByLabelText(/^Quantity/), "5");
    await user.click(screen.getByRole("button", { name: "Add stock" }));

    expect(await screen.findByText("Enter an item name.")).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it("maps a 422 loc back to the add-form field", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/inventory", () => HttpResponse.json([])),
      http.post("/api/inventory", () =>
        HttpResponse.json(
          {
            detail: [
              {
                loc: ["body", "quantity"],
                msg: "Input should be greater than or equal to 0",
                type: "greater_than_equal",
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    renderInventory();

    await user.type(screen.getByLabelText(/^Item/), "Flour");
    await user.type(screen.getByLabelText(/^Quantity/), "5");
    await user.click(screen.getByRole("button", { name: "Add stock" }));

    expect(
      await screen.findByText("Input should be greater than or equal to 0"),
    ).toBeInTheDocument();
  });

  it("renders a string `detail` rejection as a form-level banner", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/inventory", () => HttpResponse.json([])),
      http.post("/api/inventory", () =>
        HttpResponse.json(
          { detail: "unit is required when setting quantity" },
          { status: 422 },
        ),
      ),
    );
    renderInventory();

    await user.type(screen.getByLabelText(/^Item/), "Flour");
    await user.type(screen.getByLabelText(/^Quantity/), "5");
    await user.click(screen.getByRole("button", { name: "Add stock" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "unit is required when setting quantity",
    );
  });

  it("deletes a row behind a confirmation dialog", async () => {
    const user = userEvent.setup();
    let items = [
      mk({ id: 1, item: "Flour", match_name: "flour", unit_bucket: "mass" }),
    ];
    let deletedId: string | undefined;
    server.use(
      http.get("/api/inventory", () => HttpResponse.json(items)),
      http.delete("/api/inventory/:id", ({ params }) => {
        deletedId = String(params.id);
        items = [];
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderInventory();

    await user.click(
      await screen.findByRole("button", { name: "Delete Flour" }),
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("Remove this item?");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(screen.queryByText("Flour")).not.toBeInTheDocument(),
    );
    expect(deletedId).toBe("1");
  });

  it("closes the confirm dialog without deleting on cancel", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(
      http.get("/api/inventory", () =>
        HttpResponse.json([mk({ id: 1, item: "Flour" })]),
      ),
      http.delete("/api/inventory/:id", () => {
        called = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderInventory();

    await user.click(
      await screen.findByRole("button", { name: "Delete Flour" }),
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("Flour")).toBeInTheDocument();
    expect(called).toBe(false);
  });
});
