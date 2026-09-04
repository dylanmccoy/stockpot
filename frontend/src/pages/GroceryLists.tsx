import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { groceryApi } from "../api/grocery";
import type { GroceryListRead, GroceryListStatus } from "../types";
import { Badge, Button, Card, Dialog, useToast } from "../components";
import { GENERIC_ERROR_MESSAGE } from "../lib/apiError";
import { formatDateTime } from "../lib/format";
import styles from "./GroceryLists.module.css";

/** items.length / checked count — the DTO carries no server-side counts. */
function counts(list: GroceryListRead): { items: number; checked: number } {
  return {
    items: list.items.length,
    checked: list.items.filter((i) => i.checked).length,
  };
}

const STATUS_LABEL: Record<GroceryListStatus, string> = {
  active: "Active",
  archived: "Archived",
};

export default function GroceryLists() {
  const [statusFilter, setStatusFilter] = useState<GroceryListStatus>("active");
  const [pendingDelete, setPendingDelete] = useState<GroceryListRead | null>(
    null,
  );

  const queryClient = useQueryClient();
  const toast = useToast();

  // Refiltering just swaps the query key; cancellation buys nothing here, so
  // the adapter's optional `signal` is left unused (matches RecipeList).
  const { data, status, error, refetch, isFetching } = useQuery({
    queryKey: ["grocery", { status: statusFilter }],
    queryFn: () => groceryApi.list(statusFilter),
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => groceryApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grocery"] });
    },
    onError: () => {
      toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
    },
  });

  const lists = useMemo(() => data ?? [], [data]);

  function confirmDelete() {
    if (!pendingDelete) return;
    removeMutation.mutate(pendingDelete.id);
    setPendingDelete(null);
  }

  return (
    <section className={styles.page} aria-busy={isFetching || undefined}>
      <header className={styles.head}>
        <h1>Groceries</h1>
        <div
          className={styles.filter}
          role="group"
          aria-label="Filter by status"
        >
          {(["active", "archived"] as const).map((s) => (
            <Button
              key={s}
              variant={statusFilter === s ? "primary" : "secondary"}
              aria-pressed={statusFilter === s}
              onClick={() => setStatusFilter(s)}
            >
              {STATUS_LABEL[s]}
            </Button>
          ))}
        </div>
      </header>

      {status === "pending" && (
        <>
          <p role="status" className="sr-only">
            Loading grocery lists…
          </p>
          <ul className={styles.grid} aria-hidden="true">
            {Array.from({ length: 3 }, (_, i) => (
              <li key={i}>
                <div className={styles.skeleton} />
              </li>
            ))}
          </ul>
        </>
      )}

      {status === "error" && (
        <div className={styles.errorPanel} role="alert">
          <p>
            {error instanceof Error
              ? error.message
              : "Could not load grocery lists."}
          </p>
          <Button variant="secondary" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}

      {status === "success" && lists.length === 0 && (
        <div className={styles.empty}>
          <p>No {statusFilter} grocery lists.</p>
        </div>
      )}

      {status === "success" && lists.length > 0 && (
        <ul className={styles.grid}>
          {lists.map((list) => {
            const { items, checked } = counts(list);
            return (
              <li key={list.id}>
                <Card className={styles.card}>
                  <div className={styles.cardHead}>
                    <h2 className={styles.cardTitle}>
                      <Link to={`/groceries/${list.id}`}>{list.name}</Link>
                    </h2>
                    <Badge
                      tone={list.status === "active" ? "accent" : "neutral"}
                    >
                      {STATUS_LABEL[list.status]}
                    </Badge>
                  </div>
                  <p className={styles.meta}>
                    <span>
                      {checked} of {items} item{items === 1 ? "" : "s"} checked
                    </span>
                    <span>{formatDateTime(list.created_at)}</span>
                  </p>
                  <div className={styles.cardActions}>
                    <Button
                      variant="danger"
                      onClick={() => setPendingDelete(list)}
                    >
                      Delete
                    </Button>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      <Dialog
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete grocery list?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete}>
              Delete
            </Button>
          </>
        }
      >
        <p>
          “{pendingDelete?.name}” will be permanently deleted. This can’t be
          undone.
        </p>
      </Dialog>
    </section>
  );
}
