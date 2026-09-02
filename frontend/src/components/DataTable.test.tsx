import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DataTable, type Column } from "./DataTable";

interface Row {
  id: number;
  item: string;
  qty: string;
}

const columns: Column<Row>[] = [
  { key: "item", header: "Item", render: (r) => r.item },
  { key: "qty", header: "Quantity", render: (r) => r.qty, align: "end" },
];

describe("DataTable", () => {
  it("renders a real table with a caption and column-scoped headers", () => {
    render(
      <DataTable
        caption="Inventory"
        columns={columns}
        rows={[{ id: 1, item: "Flour", qty: "500 g" }]}
        rowKey={(r) => r.id}
      />,
    );
    const table = screen.getByRole("table", { name: "Inventory" });
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual(["Item", "Quantity"]);
    headers.forEach((h) => expect(h).toHaveAttribute("scope", "col"));
  });

  it("labels each cell for the stacked (mobile) layout", () => {
    render(
      <DataTable
        caption="Inventory"
        columns={columns}
        rows={[{ id: 1, item: "Flour", qty: "500 g" }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.getByRole("cell", { name: "Flour" })).toHaveAttribute(
      "data-label",
      "Item",
    );
  });

  it("shows the empty slot when there are no rows", () => {
    render(
      <DataTable
        caption="Inventory"
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        empty="No items yet"
      />,
    );
    expect(screen.getByText("No items yet")).toBeInTheDocument();
  });
});
