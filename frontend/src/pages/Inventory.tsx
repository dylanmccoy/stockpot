import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { inventoryApi } from "../api/inventory";
import type {
  InventoryItemCreate,
  InventoryItemRead,
  InventoryItemUpdate,
} from "../types";
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
  ApiError,
  GENERIC_ERROR_MESSAGE,
  hasInlineFormError,
  useFormErrors,
} from "../lib/apiError";
import { formatDateTime, formatQuantity } from "../lib/format";
import styles from "./Inventory.module.css";

const INVENTORY_KEY = ["inventory"] as const;

// Generic write conflict on the additive-upsert POST (spec §6 catalog: a `409`
// with `detail: "conflict"` from inventory `POST`). Surfaced as a toast + a
// refetch, not the verbatim "conflict" banner the string-`detail` rule would
// otherwise produce.
const STOCK_CONFLICT_MESSAGE =
  "Someone else was updating stock. We've refreshed — try again.";

const isStockConflict = (err: unknown): boolean =>
  err instanceof ApiError && err.status === 409;

// The one `409` that is NOT the generic write conflict: a PATCH `match_name`
// whose normalized value collides with another `(match_name, unit_bucket)` row.
// Its `detail` is a fixed human string and it renders inline on the field
// (spec §6 catalog row, §10.9).
const MATCH_NAME_COLLISION_DETAIL = "match_name already in use for this bucket";

const isMatchNameCollision = (err: unknown): boolean =>
  err instanceof ApiError &&
  err.status === 409 &&
  err.detail === MATCH_NAME_COLLISION_DETAIL;

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

// ── Inline edit: draft → PATCH body + client-side PATCH-rule guards ─────────
// `docs/spec.md` §5.5 enforces a small rule set on `PATCH /api/inventory/{id}`.
// A handful of those rejections are *guaranteed* from what the form already
// knows, so we block them client-side rather than round-trip a certain `422`
// (spec §10.9). The server still owns the full rule set.

// Unit token → `unit_bucket`, mirrored just far enough from
// `backend/app/units.py` (`_UNIT_TABLE`, `OPAQUE_TOKENS`) to place a typed unit.
// `lib/parseIngredientLine.ts` carries the sibling token lists for the paste
// preview; kept separate here because that one is a flat "is this a unit" Set
// while the guard needs the mass/volume/count split.
const SYNONYM_BUCKET: Record<string, "mass" | "volume" | "count"> = {
  g: "mass",
  gram: "mass",
  kg: "mass",
  mg: "mass",
  oz: "mass",
  ounce: "mass",
  lb: "mass",
  lbs: "mass",
  pound: "mass",
  ml: "volume",
  l: "volume",
  litre: "volume",
  liter: "volume",
  tsp: "volume",
  teaspoon: "volume",
  tbsp: "volume",
  tablespoon: "volume",
  cup: "volume",
  "fl-oz": "volume",
  "fl oz": "volume",
  floz: "volume",
  pint: "volume",
  quart: "volume",
  gallon: "volume",
  unit: "count",
  each: "count",
  dozen: "count",
  pair: "count",
};

const OPAQUE_UNIT_TOKENS = new Set([
  "clove",
  "slice",
  "piece",
  "stick",
  "can",
  "package",
  "pkg",
  "jar",
  "bottle",
  "box",
  "bag",
  "head",
  "bulb",
  "bunch",
  "sprig",
  "pinch",
  "handful",
  "dash",
  "splash",
]);

/** Light mirror of `normalize_unit_token`: lower, trim, drop one trailing ".",
 *  singularize the whole string ("Cups." → "cup", "boxes" → "box"). The
 *  singularize rule matches `singularize` in `lib/parseIngredientLine.ts`. */
function normalizeUnitToken(raw: string): string {
  let s = raw.trim().toLowerCase();
  if (s.endsWith(".")) s = s.slice(0, -1);
  if (s.length > 3 && /(?:ses|xes|ches|shes)$/.test(s)) return s.slice(0, -2);
  if (s.length > 1 && s.endsWith("s") && !s.endsWith("ss"))
    return s.slice(0, -1);
  return s;
}

/** The `unit_bucket` a typed unit resolves to — `"mass" | "volume" | "count" |
 *  "opaque:<token>"` — or `null` when the token is unknown (let the server
 *  decide). A blank unit is the COUNT bucket (a null `display_unit`). */
export function bucketForUnit(raw: string): string | null {
  const t = normalizeUnitToken(raw);
  if (!t) return "count";
  if (t in SYNONYM_BUCKET) return SYNONYM_BUCKET[t];
  if (OPAQUE_UNIT_TOKENS.has(t)) return `opaque:${t}`;
  return null;
}

/** The plain noun for a `unit_bucket` in error/hint copy — the `opaque:` prefix
 *  dropped so `"opaque:can"` reads as `"can"`. */
function bucketNoun(bucket: string): string {
  return bucket.startsWith("opaque:") ? bucket.slice("opaque:".length) : bucket;
}

// Short canonical unit list per bucket, for the edit hint (spec §10.9 "the
// field offers only same-bucket units"). An `opaque:` bucket has none — that
// unit can't change without a remove-and-re-add.
const BUCKET_UNITS: Record<string, string[]> = {
  mass: ["g", "kg", "mg", "oz", "lb"],
  volume: ["ml", "l", "tsp", "tbsp", "cup", "pint", "quart", "gallon"],
  count: ["unit", "each", "dozen", "pair"],
};

export function sameBucketUnits(bucket: string): string[] {
  return BUCKET_UNITS[bucket] ?? [];
}

export interface InventoryEditDraft {
  quantity: string;
  unit: string;
  matchName: string;
}

/** The edit form opens pre-filled with the row's current display values. The
 *  quantity is snapped to 6 significant figures so a raw response float
 *  (`266.1616…`) never lands in the input verbatim (spec §7.2). */
export function editDraftFrom(item: InventoryItemRead): InventoryEditDraft {
  return {
    quantity: String(Number(item.display_quantity.toPrecision(6))),
    unit: item.display_unit ?? "",
    matchName: item.match_name,
  };
}

export interface EditDraftErrors {
  quantity?: string;
  unit?: string;
  matchName?: string;
}

interface EditDraftDiff {
  matchChanged: boolean;
  qtyChanged: boolean;
  unitChanged: boolean;
  qtyValid: boolean;
}

/** Which fields the draft actually moves off the row — the single place the
 *  "what changed" question is answered, shared by the validator and the
 *  PATCH-body builder so they can't drift. */
function diffEditDraft(
  item: InventoryItemRead,
  draft: InventoryEditDraft,
): EditDraftDiff {
  const raw = draft.quantity.trim();
  const qty = Number(raw);
  const qtyValid = raw !== "" && Number.isFinite(qty) && qty >= 0;
  return {
    matchChanged: draft.matchName.trim() !== item.match_name,
    qtyValid,
    qtyChanged: qtyValid && qty !== item.display_quantity,
    unitChanged:
      normalizeUnitToken(draft.unit) !==
      normalizeUnitToken(item.display_unit ?? ""),
  };
}

/** Guards that block a PATCH which `docs/spec.md` §5.5 is certain to reject.
 *  Everything else (a real collision, an unknown unit) still goes to the
 *  server. Returns `null` when the draft is safe to send. */
export function validateEditDraft(
  item: InventoryItemRead,
  draft: InventoryEditDraft,
): EditDraftErrors | null {
  const errors: EditDraftErrors = {};
  const { qtyValid, qtyChanged, unitChanged } = diffEditDraft(item, draft);

  if (!draft.matchName.trim()) errors.matchName = "Enter a match name.";
  if (!qtyValid) errors.quantity = "Enter a quantity of zero or more.";

  const nextUnit = draft.unit.trim();
  const isCountRow = item.unit_bucket === "count";

  if (qtyChanged && !nextUnit && !isCountRow) {
    // A quantity change forces its unit into the request (decision S2); a
    // non-COUNT row can't ride along with a null unit.
    errors.unit = "Confirm the unit for the new quantity.";
  } else if (unitChanged || (!nextUnit && !isCountRow)) {
    const bucket = bucketForUnit(nextUnit);
    if (bucket !== null && bucket !== item.unit_bucket) {
      errors.unit = nextUnit
        ? `“${nextUnit}” is not a ${bucketNoun(item.unit_bucket)} unit — remove the item and re-add it to change bucket.`
        : `A ${bucketNoun(item.unit_bucket)} item needs a unit — clearing it would change the bucket.`;
    }
  }

  return Object.keys(errors).length ? errors : null;
}

/** Draft → `InventoryItemUpdate`, keyed on what actually changed (the server
 *  drives off `model_fields_set`, §5.5). A `quantity` change always carries
 *  `unit` (decision S2); a blank unit serializes as `null`. */
export function buildInventoryPatch(
  item: InventoryItemRead,
  draft: InventoryEditDraft,
): InventoryItemUpdate {
  const body: InventoryItemUpdate = {};
  const { matchChanged, qtyChanged, unitChanged } = diffEditDraft(item, draft);

  if (matchChanged) body.match_name = draft.matchName.trim();

  const unitValue = draft.unit.trim() === "" ? null : draft.unit.trim();
  if (qtyChanged) {
    body.quantity = Number(draft.quantity.trim());
    body.unit = unitValue;
  } else if (unitChanged) {
    body.unit = unitValue;
  }

  return body;
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
  const [pendingEdit, setPendingEdit] = useState<InventoryItemRead | null>(
    null,
  );
  const [editDraft, setEditDraft] = useState<InventoryEditDraft | null>(null);
  const [clientEditErrors, setClientEditErrors] = useState<EditDraftErrors>({});

  const add = useMutation({
    mutationFn: (body: InventoryItemCreate) => inventoryApi.create(body),
    onSuccess: () => {
      setDraft(emptyAddDraft());
      setClientErrors({});
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEY });
    },
    onError: (err: unknown) => {
      // Field / form-level `422`s render inline via `useFormErrors`. A write
      // conflict gets its own copy + a refetch; anything else (transport,
      // `5xx`) is the generic toast (spec §6).
      if (isStockConflict(err)) {
        toast.show(STOCK_CONFLICT_MESSAGE, { variant: "error" });
        queryClient.invalidateQueries({ queryKey: INVENTORY_KEY });
      } else if (!hasInlineFormError(err)) {
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

  const edit = useMutation({
    mutationFn: (vars: { id: number; body: InventoryItemUpdate }) =>
      inventoryApi.update(vars.id, vars.body),
    onSuccess: () => {
      setPendingEdit(null);
      setEditDraft(null);
      setClientEditErrors({});
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEY });
    },
    onError: (err: unknown) => {
      // A `match_name` collision and any `422` render inline (below). A generic
      // write conflict closes the editor with a toast + refetch; anything else
      // is the generic toast (spec §6).
      if (isMatchNameCollision(err)) return;
      if (isStockConflict(err)) {
        setPendingEdit(null);
        setEditDraft(null);
        toast.show(STOCK_CONFLICT_MESSAGE, { variant: "error" });
        queryClient.invalidateQueries({ queryKey: INVENTORY_KEY });
      } else if (!hasInlineFormError(err)) {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });

  // A `409` is handled by the toast + refetch above, so keep it off the inline
  // banner (`isFormLevelStatus` would otherwise show the bare "conflict").
  const { fieldErrors, formError } = useFormErrors(
    isStockConflict(add.error) ? null : add.error,
  );

  // The `match_name` collision is a `409` we DO want inline (on the field), so
  // it is excluded from `useFormErrors` and threaded in by hand below.
  const { fieldErrors: editFieldErrors, formError: editFormError } =
    useFormErrors(isStockConflict(edit.error) ? null : edit.error);

  const editMatchNameError =
    clientEditErrors.matchName ??
    (isMatchNameCollision(edit.error)
      ? MATCH_NAME_COLLISION_DETAIL
      : undefined) ??
    editFieldErrors["match_name"];
  const editQuantityError =
    clientEditErrors.quantity ?? editFieldErrors["quantity"];
  const editUnitError = clientEditErrors.unit ?? editFieldErrors["unit"];

  // The row's Edit button, so focus can return to it when the panel closes (§9).
  const editTriggerRef = useRef<HTMLButtonElement | null>(null);
  const editPanelRef = useRef<HTMLElement | null>(null);

  function openEdit(item: InventoryItemRead, trigger: HTMLButtonElement) {
    edit.reset();
    editTriggerRef.current = trigger;
    setClientEditErrors({});
    setEditDraft(editDraftFrom(item));
    setPendingEdit(item);
  }

  function closeEdit() {
    setPendingEdit(null);
    setEditDraft(null);
    setClientEditErrors({});
    editTriggerRef.current?.focus();
  }

  // Move focus to the first field when the panel opens (§9).
  useEffect(() => {
    if (pendingEdit) editPanelRef.current?.querySelector("input")?.focus();
  }, [pendingEdit]);

  const editUnitOptions = pendingEdit
    ? sameBucketUnits(pendingEdit.unit_bucket)
    : [];
  const editUnitHint =
    pendingEdit?.unit_bucket === "count"
      ? `Leave blank to track by count, or use ${editUnitOptions.join(", ")}.`
      : editUnitOptions.length
        ? `Use a ${bucketNoun(pendingEdit?.unit_bucket ?? "")} unit — ${editUnitOptions.join(", ")}.`
        : "This unit can't change here — remove and re-add the item to change it.";

  function submitEdit() {
    if (!pendingEdit || !editDraft) return;
    const problems = validateEditDraft(pendingEdit, editDraft);
    setClientEditErrors(problems ?? {});
    if (problems) return;
    const body = buildInventoryPatch(pendingEdit, editDraft);
    if (Object.keys(body).length === 0) {
      closeEdit(); // nothing changed — no-op
      return;
    }
    edit.mutate({ id: pendingEdit.id, body });
  }

  const setField = (next: Partial<InventoryAddDraft>) =>
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
        <div className={styles.rowActions}>
          <Button
            variant="ghost"
            aria-label={`Edit ${r.item}`}
            onClick={(e) => openEdit(r, e.currentTarget)}
          >
            Edit
          </Button>
          <Button
            variant="ghost"
            aria-label={`Delete ${r.item}`}
            onClick={() => setPendingDelete(r)}
          >
            Delete
          </Button>
        </div>
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
              onChange={(e) => setField({ item: e.target.value })}
            />
          </Field>
          <Field label="Quantity" error={quantityError} required>
            <Input
              type="number"
              min="0"
              inputMode="decimal"
              value={draft.quantity}
              onChange={(e) => setField({ quantity: e.target.value })}
            />
          </Field>
          <Field
            label="Unit"
            error={fieldErrors["unit"]}
            hint="Leave blank to track by count."
          >
            <Input
              value={draft.unit}
              onChange={(e) => setField({ unit: e.target.value })}
            />
          </Field>
          <Field
            label="Match name"
            error={fieldErrors["match_name"]}
            hint="Optional — links this stock to recipe ingredients. Defaults to the item name."
          >
            <Input
              value={draft.matchName}
              onChange={(e) => setField({ matchName: e.target.value })}
            />
          </Field>
        </div>

        <div className={styles.addActions}>
          <Button type="submit" loading={add.isPending}>
            Add stock
          </Button>
        </div>
      </form>

      {pendingEdit && editDraft && (
        <section
          ref={editPanelRef}
          className={styles.editPanel}
          aria-label={`Edit ${pendingEdit.item}`}
        >
          <form
            className={styles.editForm}
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              submitEdit();
            }}
          >
            <div className={styles.editHead}>
              <h2 className={styles.addHeading}>Edit {pendingEdit.item}</h2>
              <Button variant="ghost" onClick={closeEdit}>
                Cancel
              </Button>
            </div>

            {editFormError !== null && (
              <p className={styles.banner} role="alert">
                {editFormError}
              </p>
            )}

            <div className={styles.editMatchName}>
              <Field
                label="Match name"
                error={editMatchNameError}
                hint="Links this stock to recipe ingredients — a recipe line and a stock row meet on this name. The server stores it normalized (lower-case, trimmed)."
                required
              >
                <Input
                  value={editDraft.matchName}
                  onChange={(e) =>
                    setEditDraft((d) =>
                      d ? { ...d, matchName: e.target.value } : d,
                    )
                  }
                />
              </Field>
            </div>

            <div className={styles.editGrid}>
              <Field label="Quantity" error={editQuantityError} required>
                <Input
                  type="number"
                  min="0"
                  inputMode="decimal"
                  value={editDraft.quantity}
                  onChange={(e) =>
                    setEditDraft((d) =>
                      d ? { ...d, quantity: e.target.value } : d,
                    )
                  }
                />
              </Field>
              <Field label="Unit" error={editUnitError} hint={editUnitHint}>
                <Input
                  value={editDraft.unit}
                  onChange={(e) =>
                    setEditDraft((d) =>
                      d ? { ...d, unit: e.target.value } : d,
                    )
                  }
                />
              </Field>
            </div>

            <div className={styles.addActions}>
              <Button type="submit" loading={edit.isPending}>
                Save changes
              </Button>
            </div>
          </form>
        </section>
      )}

      {status === "pending" && (
        <>
          <p role="status" className="sr-only">
            Loading inventory…
          </p>
          <div className={styles.skeleton} aria-hidden="true" />
        </>
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
