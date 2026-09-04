import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { groceryApi } from "../api/grocery";
import type {
  GroceryListItemIn,
  GroceryListItemRead,
  GroceryListItemUpdate,
  GroceryListRead,
} from "../types";
import {
  ApiError,
  GENERIC_ERROR_MESSAGE,
  STOCK_CONFLICT_MESSAGE,
  hasInlineFormError,
  isStockConflict,
  useFormErrors,
} from "../lib/apiError";
import { formatQuantity } from "../lib/format";
import { cx } from "../lib/cx";
import { Badge, Button, Dialog, Field, Input, useToast } from "../components";
import styles from "./GroceryListDetail.module.css";

// GroceryListDetail — render + optimistic check (ticket 13a), add/edit lines
// (this ticket, 13b), submit/archive (13c). Built against the spec DTO through
// the grocery adapter (R-2), not wired to real calls here (ticket 18).

/** Count units carry no unit word (spec §7.2) — duplicated from RecipeDetail's
 *  identical helper; a few lines, kept local rather than importing across
 *  pages. */
const COUNT_UNITS: ReadonlySet<string | null> = new Set([null, "unit", "each"]);

function withUnitWord(formatted: string, unit: string | null): string {
  if (!formatted) return "";
  if (COUNT_UNITS.has(unit)) return formatted;
  return [formatted, unit].filter(Boolean).join(" ");
}

/** A grocery line's quantity, run through `formatQuantity` (spec §7.2) with its
 *  unit appended — never a raw float. Only meaningful for `nettable:true`
 *  lines; the caller checks that first (spec §7.4 — a `nettable:false` line
 *  never shows a computed number). */
export function quantityLabel(
  item: Pick<GroceryListItemRead, "quantity" | "unit">,
): string {
  return withUnitWord(formatQuantity(item.quantity, item.unit), item.unit);
}

/** A frozen line's amount actually added to inventory (`applied_*`) — shown
 *  in place of `quantityLabel` once `added_to_inventory` is true (spec §10.7:
 *  "show the amount that was added"). Same formatter, different source field. */
export function appliedLabel(
  item: Pick<GroceryListItemRead, "applied_quantity" | "applied_unit">,
): string {
  return withUnitWord(
    formatQuantity(item.applied_quantity, item.applied_unit),
    item.applied_unit,
  );
}

// ── Line drafts — add form + inline edit form share one shape ──────────────

export interface GroceryLineDraft {
  item: string;
  quantity: string;
  unit: string;
}

export const emptyLineDraft = (): GroceryLineDraft => ({
  item: "",
  quantity: "",
  unit: "",
});

/** A line's current values as edit-form strings. The quantity is snapped to 6
 *  significant figures so a raw response float never lands in the input
 *  verbatim (spec §7.2, mirrors Inventory's `editDraftFrom`). */
function lineDraftFrom(item: GroceryListItemRead): GroceryLineDraft {
  return {
    item: item.item,
    quantity:
      item.quantity == null ? "" : String(Number(item.quantity.toPrecision(6))),
    unit: item.unit ?? "",
  };
}

export interface LineDraftErrors {
  item?: string;
  quantity?: string;
}

/** Client guards that only block a guaranteed-`422` (spec §5 "Grocery": `item`
 *  1..200, `quantity` > 0 finite when set). The server owns the full rule set. */
function validateLineDraft(draft: GroceryLineDraft): LineDraftErrors | null {
  const errors: LineDraftErrors = {};
  if (!draft.item.trim()) errors.item = "Enter an item name.";
  const raw = draft.quantity.trim();
  if (raw) {
    const q = Number(raw);
    if (!Number.isFinite(q) || q <= 0) {
      errors.quantity = "Enter a quantity greater than zero.";
    }
  }
  return Object.keys(errors).length ? errors : null;
}

/** Draft → `POST .../items` body (spec §5 "Grocery"). `quantity` and `unit`
 *  are each independently settable — no atomic pair on add — but unlike the
 *  PATCH below, the backend schema requires both keys present (possibly
 *  `null`): an amount-less manual line sends `quantity: null, unit: null`
 *  explicitly rather than omitting the keys (ticket 18 re-diff). */
export function buildAddLine(draft: GroceryLineDraft): GroceryListItemIn {
  const raw = draft.quantity.trim();
  const unit = draft.unit.trim();
  return {
    item: draft.item.trim(),
    quantity: raw ? Number(raw) : null,
    unit: unit ? unit : null,
  };
}

/** Which fields the edit draft actually moves off the line — the single place
 *  the "what changed" question is answered, shared by the validator and the
 *  PATCH-body builder (mirrors Inventory's `diffEditDraft`). */
function diffLineDraft(original: GroceryListItemRead, draft: GroceryLineDraft) {
  const currentQuantity =
    original.quantity == null
      ? ""
      : String(Number(original.quantity.toPrecision(6)));
  const currentUnit = original.unit ?? "";
  return {
    itemChanged: draft.item.trim() !== original.item,
    quantityOrUnitChanged:
      draft.quantity.trim() !== currentQuantity ||
      draft.unit.trim() !== currentUnit,
  };
}

function validateEditDraft(
  original: GroceryListItemRead,
  draft: GroceryLineDraft,
): LineDraftErrors | null {
  const errors = validateLineDraft(draft) ?? {};
  // Only a real quantity/unit change needs the >0 guard re-checked against
  // *this* diff — `validateLineDraft` already covers it from the raw string.
  const { quantityOrUnitChanged } = diffLineDraft(original, draft);
  if (!quantityOrUnitChanged) delete errors.quantity;
  return Object.keys(errors).length ? errors : null;
}

/** Draft → `PATCH .../items/{id}` body (spec §5 "Grocery", rule N6): `quantity`
 *  and `unit` go in as an atomic pair whenever either one moved off the line's
 *  current value — never one without the other. `item` is independent. An
 *  unchanged draft yields `{}` (caller treats that as a no-op). */
export function buildEditPatch(
  original: GroceryListItemRead,
  draft: GroceryLineDraft,
): GroceryListItemUpdate {
  const body: GroceryListItemUpdate = {};
  const { itemChanged, quantityOrUnitChanged } = diffLineDraft(original, draft);
  if (itemChanged) body.item = draft.item.trim();
  if (quantityOrUnitChanged) {
    const raw = draft.quantity.trim();
    body.quantity = raw ? Number(raw) : null;
    const unit = draft.unit.trim();
    body.unit = unit ? unit : null;
  }
  return body;
}

// Shown once, as a toast, when an edit reclassifies a generated line to manual
// (spec §10.7 "a quiet note ... no longer netted against stock").
const RECLASSIFY_NOTE =
  "This is now a manual line — we'll stop netting it against your stock.";

// Two distinct 409s a line PATCH can hit once submit/archive exist (spec §6
// catalog): the list itself went archived out from under the editor, or —
// same wire detail ("conflict") as the R-11 generic race, but only reachable
// on this endpoint — the line was frozen by a submit that landed first.
const LIST_ARCHIVED_MESSAGE = "This list is archived.";
const FROZEN_LINE_MESSAGE = "This item was already added to inventory.";

function isListNotActive(err: unknown): boolean {
  return (
    err instanceof ApiError &&
    err.status === 409 &&
    err.detail === "list is not active"
  );
}

function NotFoundPanel() {
  return (
    <section className={styles.panel} role="alert">
      <h1>Grocery list not found</h1>
      <p className={styles.muted}>This list may have been deleted.</p>
      <Link to="/groceries">Back to grocery lists</Link>
    </section>
  );
}

export default function GroceryListDetail() {
  const { id } = useParams();
  const numeric = Number(id);
  if (!id || !Number.isInteger(numeric) || numeric <= 0) {
    return <NotFoundPanel />;
  }
  // Remount on id change so no state leaks between two lists visited in a row.
  return <GroceryListDetailView key={id} id={numeric} />;
}

function GroceryListDetailView({ id }: { id: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const queryKey = useMemo(() => ["grocery", id] as const, [id]);

  // One query per screen; request cancellation buys nothing here, so the
  // adapter's optional `signal` is left unused (matches RecipeDetail).
  const query = useQuery({
    queryKey,
    queryFn: () => groceryApi.get(id),
  });

  // The **only** optimistic mutation on this screen (spec §10.7, Q16): flip
  // the line immediately, roll back via `onError` if the server rejects it.
  // A checked-only PATCH never reclassifies the line, so nothing else in the
  // cached list needs to change.
  const checkMutation = useMutation({
    mutationFn: ({ itemId, checked }: { itemId: number; checked: boolean }) =>
      groceryApi.updateItem(id, itemId, { checked }),
    onMutate: async ({ itemId, checked }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<GroceryListRead>(queryKey);
      if (previous) {
        queryClient.setQueryData<GroceryListRead>(queryKey, {
          ...previous,
          items: previous.items.map((item) =>
            item.id === itemId ? { ...item, checked } : item,
          ),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
      toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  // Add a manual line (spec §10.7 "Add manual line").
  const [addDraft, setAddDraft] = useState<GroceryLineDraft>(emptyLineDraft());
  const [addErrors, setAddErrors] = useState<LineDraftErrors>({});
  const addMutation = useMutation({
    mutationFn: (body: GroceryListItemIn) => groceryApi.addItem(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      setAddDraft(emptyLineDraft());
      setAddErrors({});
    },
    onError: (err: unknown) => {
      if (!hasInlineFormError(err)) {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });
  const { fieldErrors: addFieldErrors, formError: addFormError } =
    useFormErrors(addMutation.error);
  const addItemError = addErrors.item ?? addFieldErrors["item"];
  const addQuantityError = addErrors.quantity ?? addFieldErrors["quantity"];

  function submitAdd() {
    const problems = validateLineDraft(addDraft);
    setAddErrors(problems ?? {});
    if (problems) return;
    addMutation.mutate(buildAddLine(addDraft));
  }

  // Edit a line's item/quantity/unit (spec §10.7 "Edit ... inline"). Only one
  // line edits at a time.
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<GroceryLineDraft | null>(null);
  const [editErrors, setEditErrors] = useState<LineDraftErrors>({});
  const editMutation = useMutation({
    mutationFn: ({
      itemId,
      body,
    }: {
      itemId: number;
      body: GroceryListItemUpdate;
      wasGenerated: boolean;
    }) => groceryApi.updateItem(id, itemId, body),
    onSuccess: (_updated, vars) => {
      queryClient.invalidateQueries({ queryKey });
      setEditingId(null);
      setEditDraft(null);
      setEditErrors({});
      if (vars.wasGenerated) {
        toast.show(RECLASSIFY_NOTE, { variant: "info" });
      }
    },
    onError: (err: unknown) => {
      // A stale editor can hit either 409: the list was archived out from
      // under it, or (same wire "conflict" detail, only possible here) the
      // line was frozen by a submit that landed first. Both close the editor
      // and refetch rather than rendering the bare detail inline.
      if (isListNotActive(err)) {
        setEditingId(null);
        setEditDraft(null);
        setEditErrors({});
        toast.show(LIST_ARCHIVED_MESSAGE, { variant: "error" });
        queryClient.invalidateQueries({ queryKey });
        return;
      }
      if (isStockConflict(err)) {
        // `isStockConflict` only checks `status === 409`, no `detail`
        // narrowing — safe here because `isListNotActive` above already
        // claimed the one other 409 this route can return (spec §5 item-PATCH
        // row: 404, 409 frozen/archived, 422). If a third 409 reason is ever
        // added to this endpoint, this blanket check will need a real
        // `detail` guard alongside it.
        setEditingId(null);
        setEditDraft(null);
        setEditErrors({});
        toast.show(FROZEN_LINE_MESSAGE, { variant: "error" });
        queryClient.invalidateQueries({ queryKey });
        return;
      }
      if (!hasInlineFormError(err)) {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });
  const { fieldErrors: editFieldErrors, formError: editFormError } =
    useFormErrors(editMutation.error);
  const editItemError = editErrors.item ?? editFieldErrors["item"];
  const editQuantityError = editErrors.quantity ?? editFieldErrors["quantity"];

  function startEdit(item: GroceryListItemRead) {
    editMutation.reset();
    setEditErrors({});
    setEditDraft(lineDraftFrom(item));
    setEditingId(item.id);
  }

  function cancelEdit() {
    editMutation.reset();
    setEditingId(null);
    setEditDraft(null);
    setEditErrors({});
  }

  function submitEdit(original: GroceryListItemRead) {
    if (!editDraft) return;
    const problems = validateEditDraft(original, editDraft);
    setEditErrors(problems ?? {});
    if (problems) return;
    const body = buildEditPatch(original, editDraft);
    if (Object.keys(body).length === 0) {
      cancelEdit(); // nothing changed — no-op
      return;
    }
    editMutation.mutate({
      itemId: original.id,
      body,
      wasGenerated: original.source === "generated",
    });
  }

  // Submit checked lines into inventory (spec §10.7 "Submit"). Forward-only:
  // re-running only picks up newly-checked lines, so the button stays live —
  // no "already submitted" state to track here.
  const [submitDialogOpen, setSubmitDialogOpen] = useState(false);
  const submitMutation = useMutation({
    mutationFn: () => groceryApi.submit(id),
    onSuccess: () => {
      setSubmitDialogOpen(false);
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (err: unknown) => {
      setSubmitDialogOpen(false);
      if (isListNotActive(err)) {
        toast.show(LIST_ARCHIVED_MESSAGE, { variant: "error" });
        queryClient.invalidateQueries({ queryKey });
      } else if (isStockConflict(err)) {
        toast.show(STOCK_CONFLICT_MESSAGE, { variant: "error" });
        queryClient.invalidateQueries({ queryKey });
      } else {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });

  // Archive a finished list (spec §10.7 "Archive"). Forward-only — no
  // un-archive; a stale attempt on an already-archived list 409s.
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false);
  const archiveMutation = useMutation({
    mutationFn: () => groceryApi.archive(id),
    onSuccess: () => {
      setArchiveDialogOpen(false);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (err: unknown) => {
      setArchiveDialogOpen(false);
      if (isListNotActive(err)) {
        toast.show(LIST_ARCHIVED_MESSAGE, { variant: "error" });
        queryClient.invalidateQueries({ queryKey });
      } else {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });

  if (query.isPending) {
    return (
      <section className={styles.page} aria-busy="true">
        <p role="status" className="sr-only">
          Loading grocery list…
        </p>
        <div className={styles.skeleton} aria-hidden="true" />
      </section>
    );
  }

  if (query.isError) {
    const notFound =
      query.error instanceof ApiError && query.error.status === 404;
    if (notFound) return <NotFoundPanel />;
    return (
      <section className={styles.panel} role="alert">
        <p>
          {query.error instanceof Error
            ? query.error.message
            : "Could not load this grocery list."}
        </p>
        <Button variant="secondary" onClick={() => query.refetch()}>
          Retry
        </Button>
      </section>
    );
  }

  const list: GroceryListRead = query.data;
  const active = list.status === "active";
  const generated = list.items.filter((i) => i.source === "generated");
  const manual = list.items.filter((i) => i.source === "manual");

  function toggle(item: GroceryListItemRead) {
    // A frozen line's PATCH 409s (spec §10.7), and so does any PATCH once the
    // list is archived — skip the round trip rather than flip-and-revert.
    if (item.added_to_inventory || !active) return;
    checkMutation.mutate({ itemId: item.id, checked: !item.checked });
  }

  const editing = { id: editingId, draft: editDraft };

  return (
    <section className={styles.page} aria-busy={query.isFetching || undefined}>
      <header className={styles.head}>
        <h1>{list.name}</h1>
        <Badge tone={active ? "accent" : "neutral"}>
          {active ? "Active" : "Archived"}
        </Badge>
      </header>

      {list.items.length === 0 ? (
        <div className={styles.empty}>
          <p>No items on this list yet.</p>
        </div>
      ) : (
        <>
          <LineGroup
            title="From your recipes"
            items={generated}
            active={active}
            onToggle={toggle}
            editing={editing}
            onStartEdit={startEdit}
            onCancelEdit={cancelEdit}
            onSubmitEdit={submitEdit}
            onEditDraftChange={setEditDraft}
            editItemError={editItemError}
            editQuantityError={editQuantityError}
            editFormError={editFormError}
            editSaving={editMutation.isPending}
          />
          <LineGroup
            title="Added manually"
            items={manual}
            active={active}
            onToggle={toggle}
            editing={editing}
            onStartEdit={startEdit}
            onCancelEdit={cancelEdit}
            onSubmitEdit={submitEdit}
            onEditDraftChange={setEditDraft}
            editItemError={editItemError}
            editQuantityError={editQuantityError}
            editFormError={editFormError}
            editSaving={editMutation.isPending}
          />
        </>
      )}

      {active && (
        <section className={styles.addSection}>
          <h2 className={styles.groupTitle}>Add an item</h2>
          <form
            className={styles.addForm}
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              submitAdd();
            }}
          >
            {addFormError !== null && (
              <p className={styles.banner} role="alert">
                {addFormError}
              </p>
            )}
            <div className={styles.addGrid}>
              <Field label="Item" error={addItemError}>
                <Input
                  value={addDraft.item}
                  onChange={(e) =>
                    setAddDraft((d) => ({ ...d, item: e.target.value }))
                  }
                />
              </Field>
              <Field label="Quantity" error={addQuantityError}>
                <Input
                  type="number"
                  min="0"
                  step="any"
                  inputMode="decimal"
                  value={addDraft.quantity}
                  onChange={(e) =>
                    setAddDraft((d) => ({ ...d, quantity: e.target.value }))
                  }
                />
              </Field>
              <Field label="Unit">
                <Input
                  value={addDraft.unit}
                  onChange={(e) =>
                    setAddDraft((d) => ({ ...d, unit: e.target.value }))
                  }
                />
              </Field>
            </div>
            <div className={styles.addActions}>
              <Button type="submit" loading={addMutation.isPending}>
                Add item
              </Button>
            </div>
          </form>
        </section>
      )}

      {active && (
        <section className={styles.actions}>
          <Button variant="primary" onClick={() => setSubmitDialogOpen(true)}>
            Submit checked items to inventory
          </Button>
          <Button
            variant="secondary"
            onClick={() => setArchiveDialogOpen(true)}
          >
            Archive list
          </Button>
        </section>
      )}

      <Dialog
        open={submitDialogOpen}
        onClose={() => setSubmitDialogOpen(false)}
        title="Add checked items to inventory?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setSubmitDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={submitMutation.isPending}
              onClick={() => submitMutation.mutate()}
            >
              Add to inventory
            </Button>
          </>
        }
      >
        <p>
          This adds every checked, unfrozen, quantified line to your inventory.
          It can’t be undone. You can keep shopping and submit again later for
          anything newly checked.
        </p>
      </Dialog>

      <Dialog
        open={archiveDialogOpen}
        onClose={() => setArchiveDialogOpen(false)}
        title="Archive this list?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setArchiveDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="secondary"
              loading={archiveMutation.isPending}
              onClick={() => archiveMutation.mutate()}
            >
              Archive
            </Button>
          </>
        }
      >
        <p>
          “{list.name}” will be archived. You won’t be able to check off or add
          items on it afterward.
        </p>
      </Dialog>
    </section>
  );
}

interface EditingState {
  id: number | null;
  draft: GroceryLineDraft | null;
}

function LineGroup({
  title,
  items,
  active,
  onToggle,
  editing,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
  onEditDraftChange,
  editItemError,
  editQuantityError,
  editFormError,
  editSaving,
}: {
  title: string;
  items: GroceryListItemRead[];
  active: boolean;
  onToggle: (item: GroceryListItemRead) => void;
  editing: EditingState;
  onStartEdit: (item: GroceryListItemRead) => void;
  onCancelEdit: () => void;
  onSubmitEdit: (item: GroceryListItemRead) => void;
  onEditDraftChange: (draft: GroceryLineDraft) => void;
  editItemError: string | undefined;
  editQuantityError: string | undefined;
  editFormError: string | null;
  editSaving: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <section className={styles.group}>
      <h2 className={styles.groupTitle}>{title}</h2>
      <ul className={styles.lines}>
        {items.map((item) => (
          <GroceryLine
            key={item.id}
            item={item}
            active={active}
            onToggle={onToggle}
            editingDraft={editing.id === item.id ? editing.draft : null}
            onStartEdit={onStartEdit}
            onCancelEdit={onCancelEdit}
            onSubmitEdit={onSubmitEdit}
            onEditDraftChange={onEditDraftChange}
            editItemError={editItemError}
            editQuantityError={editQuantityError}
            editFormError={editFormError}
            editSaving={editSaving}
          />
        ))}
      </ul>
    </section>
  );
}

function GroceryLine({
  item,
  active,
  onToggle,
  editingDraft,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
  onEditDraftChange,
  editItemError,
  editQuantityError,
  editFormError,
  editSaving,
}: {
  item: GroceryListItemRead;
  active: boolean;
  onToggle: (item: GroceryListItemRead) => void;
  editingDraft: GroceryLineDraft | null;
  onStartEdit: (item: GroceryListItemRead) => void;
  onCancelEdit: () => void;
  onSubmitEdit: (item: GroceryListItemRead) => void;
  onEditDraftChange: (draft: GroceryLineDraft) => void;
  editItemError: string | undefined;
  editQuantityError: string | undefined;
  editFormError: string | null;
  editSaving: boolean;
}) {
  const frozen = item.added_to_inventory;
  // A frozen line's PATCH 409s, and so does any PATCH once the list is
  // archived (spec §10.7: "Frozen lines ... PATCH/DELETE affordances hidden",
  // "Archived list → all mutation affordances hidden").
  const disabled = frozen || !active;

  if (editingDraft) {
    return (
      <li>
        <form
          className={styles.editLine}
          aria-label={`Edit ${item.item}`}
          onSubmit={(e) => {
            e.preventDefault();
            onSubmitEdit(item);
          }}
        >
          {editFormError !== null && (
            <p className={styles.banner} role="alert">
              {editFormError}
            </p>
          )}
          <div className={styles.editGrid}>
            <Field label="Item" error={editItemError}>
              <Input
                value={editingDraft.item}
                onChange={(e) =>
                  onEditDraftChange({ ...editingDraft, item: e.target.value })
                }
              />
            </Field>
            <Field label="Quantity" error={editQuantityError}>
              <Input
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                value={editingDraft.quantity}
                onChange={(e) =>
                  onEditDraftChange({
                    ...editingDraft,
                    quantity: e.target.value,
                  })
                }
              />
            </Field>
            <Field label="Unit">
              <Input
                value={editingDraft.unit}
                onChange={(e) =>
                  onEditDraftChange({ ...editingDraft, unit: e.target.value })
                }
              />
            </Field>
          </div>
          <div className={styles.editActions}>
            <Button type="submit" loading={editSaving}>
              Save
            </Button>
            <Button type="button" variant="ghost" onClick={onCancelEdit}>
              Cancel
            </Button>
          </div>
        </form>
      </li>
    );
  }

  return (
    <li>
      <div
        className={cx(
          styles.line,
          item.checked && styles.lineChecked,
          frozen && styles.lineFrozen,
        )}
      >
        <label className={styles.lineMain}>
          <input
            type="checkbox"
            className={styles.checkbox}
            checked={item.checked}
            disabled={disabled}
            onChange={() => onToggle(item)}
            aria-label={item.item}
          />
          <span className={styles.lineBody}>
            <span className={styles.lineItem}>{item.item}</span>
            {/* Frozen: the applied amount below is the number that matters —
                showing the (now moot) current quantity too would just repeat
                it (spec §10.7 "show the amount that was added"). */}
            {!frozen &&
              (item.nettable ? (
                <span className={styles.lineQty}>
                  {quantityLabel(item) || "—"}
                </span>
              ) : (
                <span className={styles.uncertain}>
                  <Badge tone="warn">amount uncertain</Badge>
                  <span className={styles.uncertainNote}>
                    buy based on what you find you’re short.
                  </span>
                </span>
              ))}
          </span>
        </label>
        {frozen && (
          <span className={styles.frozenMeta}>
            <Badge tone="ok">Added to inventory</Badge>
            <span className={styles.appliedQty}>{appliedLabel(item)}</span>
          </span>
        )}
        {!frozen && active && (
          <Button
            variant="ghost"
            aria-label={`Edit ${item.item}`}
            onClick={() => onStartEdit(item)}
          >
            Edit
          </Button>
        )}
      </div>
    </li>
  );
}
