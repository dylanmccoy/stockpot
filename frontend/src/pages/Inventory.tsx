import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { inventoryApi } from "../api/inventory";
import type { InventoryItemCreate, InventoryItemRead } from "../types";
import {
  Button,
  DataTable,
  Dialog,
  Field,
  Input,
  useToast,
} from "../components";
import type { Column } from "../components";
import {
  GENERIC_ERROR_MESSAGE,
  hasInlineFormError,
  useFormErrors,
} from "../lib/apiError";
import { formatDateTime, formatQuantity } from "../lib/format";
import styles from "./Inventory.module.css";

const INVENTORY_KEY = ["inventory"] as const;

// ── Add-form draft → POST body (the one serialization seam) ────────────────
// The form holds every field as a string; `buildInventoryCreate` is the single
// place a draft becomes the POST body (spec §10.9 / §5 "Inventory").

export interface InventoryAddDraft {
  item: string;
  quantity: string;
  unit: string;
  matchName: string;
}

export const emptyAddDraft = (): InventoryAddDraft => ({
  item: "",
  quantity: "",
  unit: "",
  matchName: "",
});

export interface AddDraftErrors {
  item?: string;
  quantity?: string;
}

/** Client guards that only block a guaranteed-`422` POST (spec §5 "Inventory").
 *  The server owns the full rule set; this keeps the obvious mistakes local. */
export function validateAddDraft(
  draft: InventoryAddDraft,
): AddDraftErrors | null {
  const errors: AddDraftErrors = {};
  if (!draft.item.trim()) errors.item = "Enter an item name.";
  const raw = draft.quantity.trim();
  const q = Number(raw);
  if (!raw || !Number.isFinite(q) || q < 0) {
    errors.quantity = "Enter a quantity of zero or more.";
  }
  return Object.keys(errors).length ? errors : null;
}

/** Draft → `InventoryItemCreate`. A blank `unit` is omitted (the server files
 *  the row in the COUNT bucket); a blank `match_name` is omitted (the server
 *  derives it from the item). Both are the additive-upsert key — a matching
 *  `(match_name, unit_bucket)` row gains quantity rather than a new row
 *  appearing (spec §10.9). */
export function buildInventoryCreate(
  draft: InventoryAddDraft,
): InventoryItemCreate {
  const body: InventoryItemCreate = {
    item: draft.item.trim(),
    quantity: Number(draft.quantity.trim()),
  };
  const unit = draft.unit.trim();
  if (unit) body.unit = unit;
  const matchName = draft.matchName.trim();
  if (matchName) body.match_name = matchName;
  return body;
}

/** Case-insensitive order by match name, then unit bucket — mirrors the server
 *  order (`match_name ASC, unit_bucket ASC`), applied defensively so the table
 *  still reads right if that ever slips (spec §10.9). */
export function sortInventory(items: InventoryItemRead[]): InventoryItemRead[] {
  return [...items].sort(
    (a, b) =>
      a.match_name.localeCompare(b.match_name, undefined, {
        sensitivity: "base",
      }) ||
      a.unit_bucket.localeCompare(b.unit_bucket, undefined, {
        sensitivity: "base",
      }),
  );
}

/** The stock quantity as one display string: `formatQuantity` snaps the number
 *  (spec §7.2), the display unit trails it. A COUNT row carries a null unit and
 *  renders as the bare count. */
export function stockLabel(item: InventoryItemRead): string {
  const quantity = formatQuantity(item.display_quantity, item.display_unit);
  return item.display_unit ? `${quantity} ${item.display_unit}` : quantity;
}

export default function Inventory() {
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data, status, error, refetch, isFetching } = useQuery({
    queryKey: INVENTORY_KEY,
    queryFn: () => inventoryApi.list(),
  });

  const [draft, setDraft] = useState<InventoryAddDraft>(emptyAddDraft);
  const [clientErrors, setClientErrors] = useState<AddDraftErrors>({});
  const [pendingDelete, setPendingDelete] = useState<InventoryItemRead | null>(
    null,
  );

  const add = useMutation({
    mutationFn: (body: InventoryItemCreate) => inventoryApi.create(body),
    onSuccess: () => {
      setDraft(emptyAddDraft());
      setClientErrors({});
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEY });
    },
    onError: (err: unknown) => {
      // Field / form-level `422`s render inline via `useFormErrors`; anything
      // else (transport, `5xx`) is a toast (spec §6).
      if (!hasInlineFormError(err)) {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });

  const del = useMutation({
    mutationFn: (id: number) => inventoryApi.remove(id),
    onSuccess: () => {
      setPendingDelete(null);
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEY });
    },
    onError: () => {
      setPendingDelete(null);
      toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
    },
  });

  const { fieldErrors, formError } = useFormErrors(add.error);

  const patch = (next: Partial<InventoryAddDraft>) =>
    setDraft((d) => ({ ...d, ...next }));

  function onAdd(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const problems = validateAddDraft(draft);
    setClientErrors(problems ?? {});
    if (problems) return;
    add.mutate(buildInventoryCreate(draft));
  }

  const rows = useMemo(() => sortInventory(data ?? []), [data]);

  const columns: Column<InventoryItemRead>[] = [
    { key: "item", header: "Item", render: (r) => r.item },
    { key: "match_name", header: "Match name", render: (r) => r.match_name },
    { key: "unit_bucket", header: "Unit bucket", render: (r) => r.unit_bucket },
    { key: "quantity", header: "In stock", align: "end", render: stockLabel },
    {
      key: "updated_at",
      header: "Last updated",
      render: (r) => formatDateTime(r.updated_at),
    },
    {
      key: "actions",
      header: "Actions",
      align: "end",
      render: (r) => (
        <Button
          variant="ghost"
          aria-label={`Delete ${r.item}`}
          onClick={() => setPendingDelete(r)}
        >
          Delete
        </Button>
      ),
    },
  ];

  const itemError = fieldErrors["item"] ?? clientErrors.item;
  const quantityError = fieldErrors["quantity"] ?? clientErrors.quantity;

  return (
    <section className={styles.page} aria-busy={isFetching || undefined}>
      <header className={styles.head}>
        <h1>Inventory</h1>
      </header>

      <form className={styles.addForm} onSubmit={onAdd} noValidate>
        <h2 className={styles.addHeading}>Add stock</h2>
        <p className={styles.addNote}>
          Adding stock that matches an existing item and unit tops up that row
          instead of creating a new one.
        </p>

        {formError !== null && (
          <p className={styles.banner} role="alert">
            {formError}
          </p>
        )}

        <div className={styles.addGrid}>
          <Field label="Item" error={itemError} required>
            <Input
              value={draft.item}
              onChange={(e) => patch({ item: e.target.value })}
            />
          </Field>
          <Field label="Quantity" error={quantityError} required>
            <Input
              type="number"
              min="0"
              inputMode="decimal"
              value={draft.quantity}
              onChange={(e) => patch({ quantity: e.target.value })}
            />
          </Field>
          <Field
            label="Unit"
            error={fieldErrors["unit"]}
            hint="Leave blank to track by count."
          >
            <Input
              value={draft.unit}
              onChange={(e) => patch({ unit: e.target.value })}
            />
          </Field>
          <Field
            label="Match name"
            error={fieldErrors["match_name"]}
            hint="Optional — links this stock to recipe ingredients. Defaults to the item name."
          >
            <Input
              value={draft.matchName}
              onChange={(e) => patch({ matchName: e.target.value })}
            />
          </Field>
        </div>

        <div className={styles.addActions}>
          <Button type="submit" loading={add.isPending}>
            Add stock
          </Button>
        </div>
      </form>

      {status === "pending" && (
        <p role="status" className={styles.muted}>
          Loading inventory…
        </p>
      )}

      {status === "error" && (
        <div className={styles.errorPanel} role="alert">
          <p>
            {error instanceof Error
              ? error.message
              : "Could not load inventory."}
          </p>
          <Button variant="secondary" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}

      {status === "success" && (
        <DataTable
          caption="Everything the household has in stock, ordered by match name"
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          empty="No stock yet — add an item above."
        />
      )}

      <Dialog
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Remove this item?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={del.isPending}
              onClick={() => pendingDelete && del.mutate(pendingDelete.id)}
            >
              Delete
            </Button>
          </>
        }
      >
        <p>
          “{pendingDelete?.item}” will be removed from inventory. This can’t be
          undone.
        </p>
      </Dialog>
    </section>
  );
}
