import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { groceryApi } from "../api/grocery";
import type { GroceryListItemRead, GroceryListRead } from "../types";
import { ApiError, GENERIC_ERROR_MESSAGE } from "../lib/apiError";
import { formatQuantity } from "../lib/format";
import { cx } from "../lib/cx";
import { Badge, Button, useToast } from "../components";
import styles from "./GroceryListDetail.module.css";

// GroceryListDetail — render + the optimistic check/uncheck (spec §10.7,
// ticket 13a). Inline edit and "add a manual line" land in 13b; submit /
// archive in 13c. Built against the spec DTO through the grocery adapter
// (R-2), not wired to real calls here (ticket 18).

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
          />
          <LineGroup
            title="Added manually"
            items={manual}
            active={active}
            onToggle={toggle}
          />
        </>
      )}
    </section>
  );
}

function LineGroup({
  title,
  items,
  active,
  onToggle,
}: {
  title: string;
  items: GroceryListItemRead[];
  active: boolean;
  onToggle: (item: GroceryListItemRead) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className={styles.group}>
      <h2 className={styles.groupTitle}>{title}</h2>
      <ul className={styles.lines}>
        {items.map((item) => (
          <GroceryLine key={item.id} item={item} active={active} onToggle={onToggle} />
        ))}
      </ul>
    </section>
  );
}

function GroceryLine({
  item,
  active,
  onToggle,
}: {
  item: GroceryListItemRead;
  active: boolean;
  onToggle: (item: GroceryListItemRead) => void;
}) {
  const frozen = item.added_to_inventory;
  // A frozen line's PATCH 409s, and so does any PATCH once the list is
  // archived (spec §10.7: "Archived list → all mutation affordances hidden");
  // the checkbox itself is the only affordance this ticket renders.
  const disabled = frozen || !active;
  return (
    <li>
      <label
        className={cx(
          styles.line,
          item.checked && styles.lineChecked,
          frozen && styles.lineFrozen,
        )}
      >
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
          {item.nettable ? (
            <span className={styles.lineQty}>{quantityLabel(item) || "—"}</span>
          ) : (
            <span className={styles.uncertain}>
              <Badge tone="warn">amount uncertain</Badge>
              <span className={styles.uncertainNote}>
                buy based on what you find you’re short.
              </span>
            </span>
          )}
        </span>
        {frozen && <Badge tone="ok">Added to inventory</Badge>}
      </label>
    </li>
  );
}
