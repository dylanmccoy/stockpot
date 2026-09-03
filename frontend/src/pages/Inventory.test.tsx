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
  bucketForUnit,
  buildInventoryCreate,
  buildInventoryPatch,
  editDraftFrom,
  emptyAddDraft,
  sameBucketUnits,
  sortInventory,
  stockLabel,
  validateAddDraft,
  validateEditDraft,
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

// ── pure: the inline-edit seams ─────────────────────────────────────────────

describe("bucketForUnit", () => {
  it("maps mass / volume / count synonyms to their bucket", () => {
    expect(bucketForUnit("kg")).toBe("mass");
    expect(bucketForUnit("Grams.")).toBe("mass");
    expect(bucketForUnit("tbsp")).toBe("volume");
    expect(bucketForUnit("cups")).toBe("volume");
    expect(bucketForUnit("dozen")).toBe("count");
  });

  it("brackets an opaque token as opaque:<token> and a blank unit as count", () => {
    expect(bucketForUnit("cans")).toBe("opaque:can");
    expect(bucketForUnit("")).toBe("count");
    expect(bucketForUnit("   ")).toBe("count");
  });

  it("returns null for an unknown token (server decides)", () => {
    expect(bucketForUnit("blorp")).toBeNull();
  });
});

describe("sameBucketUnits", () => {
  it("lists canonical units for a known bucket, nothing for opaque", () => {
    expect(sameBucketUnits("mass")).toContain("kg");
    expect(sameBucketUnits("count")).toEqual(["unit", "each", "dozen", "pair"]);
    expect(sameBucketUnits("opaque:can")).toEqual([]);
  });
});

describe("editDraftFrom", () => {
  it("pre-fills from the row's display values; a null unit becomes ''", () => {
    expect(
      editDraftFrom(
        mk({ display_quantity: 3, display_unit: null, match_name: "eggs" }),
      ),
    ).toEqual({ quantity: "3", unit: "", matchName: "eggs" });
  });

  it("snaps a raw response float so it never lands in the input verbatim", () => {
    expect(
      editDraftFrom(mk({ display_quantity: 266.1616, display_unit: "ml" }))
        .quantity,
    ).toBe("266.162");
  });
});

describe("validateEditDraft", () => {
  const massRow = mk({
    unit_bucket: "mass",
    display_unit: "g",
    display_quantity: 1000,
    match_name: "flour",
  });

  it("passes an in-bucket quantity + unit change", () => {
    expect(
      validateEditDraft(massRow, {
        quantity: "0.5",
        unit: "kg",
        matchName: "flour",
      }),
    ).toBeNull();
  });

  it("blocks a quantity change that drops the unit on a non-COUNT row", () => {
    expect(
      validateEditDraft(massRow, {
        quantity: "500",
        unit: "",
        matchName: "flour",
      }),
    ).toEqual({ unit: "Confirm the unit for the new quantity." });
  });

  it("blocks a unit that lands in a different bucket", () => {
    expect(
      validateEditDraft(massRow, {
        quantity: "1000",
        unit: "can",
        matchName: "flour",
      })?.unit,
    ).toMatch(/not a mass unit/);
  });

  it("blocks clearing the unit on a non-COUNT row", () => {
    expect(
      validateEditDraft(massRow, {
        quantity: "1000",
        unit: "",
        matchName: "flour",
      })?.unit,
    ).toMatch(/needs a unit/);
  });

  it("allows a COUNT row to change quantity with no unit", () => {
    const countRow = mk({
      unit_bucket: "count",
      display_unit: null,
      display_quantity: 6,
    });
    expect(
      validateEditDraft(countRow, {
        quantity: "12",
        unit: "",
        matchName: "eggs",
      }),
    ).toBeNull();
  });

  it("flags a blank match name", () => {
    expect(
      validateEditDraft(massRow, {
        quantity: "1000",
        unit: "g",
        matchName: "  ",
      }),
    ).toEqual({ matchName: "Enter a match name." });
  });
});

describe("buildInventoryPatch", () => {
  const row = mk({
    match_name: "flour",
    unit_bucket: "mass",
    display_unit: "g",
    display_quantity: 1000,
  });

  it("sends only what changed", () => {
    expect(
      buildInventoryPatch(row, {
        quantity: "1000",
        unit: "g",
        matchName: "flour",
      }),
    ).toEqual({});
    expect(
      buildInventoryPatch(row, {
        quantity: "1000",
        unit: "g",
        matchName: "Bread Flour",
      }),
    ).toEqual({ match_name: "Bread Flour" });
    expect(
      buildInventoryPatch(row, {
        quantity: "1000",
        unit: "kg",
        matchName: "flour",
      }),
    ).toEqual({ unit: "kg" });
  });

  it("rides `unit` along with any `quantity` change (decision S2)", () => {
    expect(
      buildInventoryPatch(row, {
        quantity: "500",
        unit: "g",
        matchName: "flour",
      }),
    ).toEqual({ quantity: 500, unit: "g" });
  });

  it("serializes a blank unit as null", () => {
    const countRow = mk({
      unit_bucket: "count",
      display_unit: "each",
      display_quantity: 6,
      match_name: "eggs",
    });
    expect(
      buildInventoryPatch(countRow, {
        quantity: "6",
        unit: "",
        matchName: "eggs",
      }),
    ).toEqual({ unit: null });
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

  it("on a 409 add conflict, toasts + refetches instead of a bare 'conflict' banner", async () => {
    const user = userEvent.setup();
    let getCalls = 0;
    server.use(
      http.get("/api/inventory", () => {
        getCalls += 1;
        return HttpResponse.json([]);
      }),
      http.post("/api/inventory", () =>
        HttpResponse.json({ detail: "conflict" }, { status: 409 }),
      ),
    );
    renderInventory();

    await screen.findByText("No stock yet — add an item above.");
    const getsBeforeAdd = getCalls;

    await user.type(screen.getByLabelText(/^Item/), "Flour");
    await user.type(screen.getByLabelText(/^Quantity/), "5");
    await user.click(screen.getByRole("button", { name: "Add stock" }));

    expect(
      await screen.findByText(/Someone else was updating stock/),
    ).toBeInTheDocument();
    expect(screen.queryByText("conflict")).not.toBeInTheDocument();
    await waitFor(() => expect(getCalls).toBeGreaterThan(getsBeforeAdd));
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

// ── flow: inline edit + PATCH rules + match_name 409 vs MSW ──────────────────

describe("Inventory edit panel", () => {
  // sampleInventoryItem: mass row, "flour" / "g" / 1000.
  const massItem = () =>
    mk({ id: 1, item: "Flour", match_name: "flour", unit_bucket: "mass" });

  const editPanel = () => screen.getByRole("region", { name: "Edit Flour" });

  /** Open the per-row inline edit panel and return it, with a PATCH spy. */
  async function openEdit(user: ReturnType<typeof userEvent.setup>) {
    let patched: unknown = null;
    server.use(
      http.get("/api/inventory", () => HttpResponse.json([massItem()])),
      http.patch("/api/inventory/:id", async ({ request }) => {
        patched = await request.json();
        return HttpResponse.json(massItem());
      }),
    );
    renderInventory();
    await user.click(await screen.findByRole("button", { name: "Edit Flour" }));
    return { panel: editPanel(), getPatched: () => patched };
  }

  it("opens an on-page panel (not a modal) with focus on the first field", async () => {
    const user = userEvent.setup();
    await openEdit(user);
    expect(editPanel()).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(within(editPanel()).getByLabelText(/^Match name/)).toHaveFocus();
  });

  it("blocks the PATCH and shows a reason when a quantity change drops the unit", async () => {
    const user = userEvent.setup();
    const { panel, getPatched } = await openEdit(user);

    await user.clear(within(panel).getByLabelText("Unit"));
    await user.clear(within(panel).getByLabelText(/^Quantity/));
    await user.type(within(panel).getByLabelText(/^Quantity/), "500");
    await user.click(
      within(panel).getByRole("button", { name: "Save changes" }),
    );

    expect(
      within(panel).getByText("Confirm the unit for the new quantity."),
    ).toBeInTheDocument();
    expect(getPatched()).toBeNull();
  });

  it("blocks the PATCH when the unit would change bucket", async () => {
    const user = userEvent.setup();
    const { panel, getPatched } = await openEdit(user);

    await user.clear(within(panel).getByLabelText("Unit"));
    await user.type(within(panel).getByLabelText("Unit"), "can");
    await user.click(
      within(panel).getByRole("button", { name: "Save changes" }),
    );

    expect(within(panel).getByText(/not a mass unit/)).toBeInTheDocument();
    expect(getPatched()).toBeNull();
  });

  it("blocks the PATCH when the unit is cleared on a non-COUNT row", async () => {
    const user = userEvent.setup();
    const { panel, getPatched } = await openEdit(user);

    await user.clear(within(panel).getByLabelText("Unit"));
    await user.click(
      within(panel).getByRole("button", { name: "Save changes" }),
    );

    expect(within(panel).getByText(/needs a unit/)).toBeInTheDocument();
    expect(getPatched()).toBeNull();
  });

  it("sends a valid { quantity, unit } PATCH and reflects it in the row", async () => {
    const user = userEvent.setup();
    let items = [massItem()];
    let patched: unknown;
    server.use(
      http.get("/api/inventory", () => HttpResponse.json(items)),
      http.patch("/api/inventory/:id", async ({ request }) => {
        patched = await request.json();
        const updated = mk({
          id: 1,
          item: "Flour",
          match_name: "flour",
          unit_bucket: "mass",
          display_unit: "g",
          display_quantity: 500,
        });
        items = [updated];
        return HttpResponse.json(updated);
      }),
    );
    renderInventory();

    await user.click(await screen.findByRole("button", { name: "Edit Flour" }));
    const panel = editPanel();
    await user.clear(within(panel).getByLabelText(/^Quantity/));
    await user.type(within(panel).getByLabelText(/^Quantity/), "500");
    await user.click(
      within(panel).getByRole("button", { name: "Save changes" }),
    );

    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "Edit Flour" }),
      ).not.toBeInTheDocument(),
    );
    expect(patched).toEqual({ quantity: 500, unit: "g" });
    const table = screen.getByRole("table");
    expect(within(table).getByText("500 g")).toBeInTheDocument();
  });

  it("shows a match_name 409 collision inline on the field", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/inventory", () => HttpResponse.json([massItem()])),
      http.patch("/api/inventory/:id", () =>
        HttpResponse.json(
          { detail: "match_name already in use for this bucket" },
          { status: 409 },
        ),
      ),
    );
    renderInventory();

    await user.click(await screen.findByRole("button", { name: "Edit Flour" }));
    const panel = editPanel();
    await user.clear(within(panel).getByLabelText(/^Match name/));
    await user.type(within(panel).getByLabelText(/^Match name/), "sugar");
    await user.click(
      within(panel).getByRole("button", { name: "Save changes" }),
    );

    expect(
      await within(panel).findByText(
        "match_name already in use for this bucket",
      ),
    ).toBeInTheDocument();
    // still open for the user to fix the name
    expect(editPanel()).toBeInTheDocument();
  });

  it("Cancel closes the panel and returns focus to the row's Edit button", async () => {
    const user = userEvent.setup();
    await openEdit(user);

    await user.click(
      within(editPanel()).getByRole("button", { name: "Cancel" }),
    );

    expect(
      screen.queryByRole("region", { name: "Edit Flour" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Flour" })).toHaveFocus();
  });
});
