import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Dialog, Field, Input, Stepper } from "../components";
import { groceryApi } from "../api/grocery";
import { recipesApi } from "../api/recipes";
import { ApiError, GENERIC_ERROR_MESSAGE } from "../lib/apiError";
import type { GroceryListRead, RecipeRead } from "../types";
import styles from "./GroceryCreateDialog.module.css";

/** Mirrors the server default (`"Groceries <UTC date>"`, spec §5 Grocery) — used
 *  only as the name-field placeholder; an empty name lets the server fill it. */
export function defaultGroceryName(now = new Date()): string {
  return `Groceries ${now.toISOString().slice(0, 10)}`;
}

export interface GroceryCreateDialogProps {
  open: boolean;
  /** Selected recipes, parent-derived as `selection ∩ ["recipes"]` — stays live
   *  so a drop / refetch shrinks the row list. */
  recipes: RecipeRead[];
  onClose: () => void;
  /** Remove one recipe from the parent's selection (the R-13 recovery path). */
  onDrop: (id: number) => void;
  onCreated: (list: GroceryListRead) => void;
}

type GoneRecipe = Pick<RecipeRead, "id" | "title">;

/**
 * Turns the RecipeList multi-selection into a named grocery list (spec §10.5).
 * A per-recipe multiplier `Stepper` (default `1×`) — the only point multipliers
 * are set, since `POST /api/grocery` takes them at create only — plus an
 * optional name. A `422` because a `recipe_id` vanished (R-13) refetches
 * `["recipes"]`, names the gone recipes, and offers to drop them and retry.
 *
 * Built against the spec DTO through the grocery adapter (R-2); wired to real
 * calls in ticket 18.
 */
export function GroceryCreateDialog({
  open,
  recipes,
  onClose,
  onDrop,
  onCreated,
}: GroceryCreateDialogProps) {
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [multipliers, setMultipliers] = useState<Record<number, number>>({});
  const [gone, setGone] = useState<GoneRecipe[]>([]);
  // A form-level banner for a 422 the recovery path can't explain (spec §6).
  const [formError, setFormError] = useState<string | null>(null);

  // Fresh dialog each time it opens: default name, default multipliers, no
  // pending recovery or error.
  useEffect(() => {
    if (open) {
      setName("");
      setMultipliers({});
      setGone([]);
      setFormError(null);
    }
  }, [open]);

  const multiplierFor = (id: number) => multipliers[id] ?? 1;

  const create = useMutation({
    mutationFn: () => {
      const recipe_ids = recipes.map((r) => r.id);
      const body = {
        recipe_ids,
        multipliers: Object.fromEntries(
          recipe_ids.map((id) => [id, multiplierFor(id)]),
        ),
        ...(name.trim() ? { name: name.trim() } : {}),
      };
      return groceryApi.create(body);
    },
    onSuccess: (list) => onCreated(list),
    onError: async (err: unknown) => {
      // R-13: a 422 can mean a selected recipe was deleted meanwhile. Re-diff
      // the selection against a fresh list; if that explains it, offer the
      // recovery path instead of a dead-end error.
      if (err instanceof ApiError && err.status === 422) {
        const submittedIds = recipes.map((r) => r.id);
        const titleById = new Map(recipes.map((r) => [r.id, r.title]));
        try {
          const fresh = await queryClient.fetchQuery({
            queryKey: ["recipes"],
            queryFn: () => recipesApi.list(),
          });
          const liveIds = new Set(fresh.map((r) => r.id));
          const missing = submittedIds.filter((id) => !liveIds.has(id));
          if (missing.length > 0) {
            setGone(
              missing.map((id) => ({
                id,
                title: titleById.get(id) ?? `Recipe ${id}`,
              })),
            );
            setFormError(null);
            return;
          }
        } catch {
          // fall through to the generic surface
        }
      }
      setGone([]);
      setFormError(
        err instanceof ApiError && typeof err.detail === "string"
          ? err.detail
          : GENERIC_ERROR_MESSAGE,
      );
    },
  });

  const dropAll = () => {
    for (const g of gone) onDrop(g.id);
    setGone([]);
    setFormError(null);
  };

  const blocked = recipes.length === 0 || gone.length > 0;

  const one = gone.length === 1;
  const goneMessage = one
    ? `“${gone[0]?.title}” was deleted and can’t be added to a list.`
    : `${gone.length} selected recipes were deleted and can’t be added to a list.`;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Create grocery list"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={create.isPending}
            disabled={blocked}
            onClick={() => create.mutate()}
          >
            Create list
          </Button>
        </>
      }
    >
      {gone.length > 0 && (
        <div className={styles.recovery} role="alert">
          <p>{goneMessage}</p>
          {!one && (
            <ul className={styles.goneList}>
              {gone.map((g) => (
                <li key={g.id}>{g.title}</li>
              ))}
            </ul>
          )}
          <Button variant="secondary" onClick={dropAll}>
            {one ? "Remove it and continue" : "Remove them and continue"}
          </Button>
        </div>
      )}

      {formError && gone.length === 0 && (
        <p className={styles.error} role="alert">
          {formError}
        </p>
      )}

      <Field label="List name">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={defaultGroceryName()}
        />
      </Field>

      <p className={styles.rowsLabel}>Amount to shop for</p>
      <ul className={styles.rows}>
        {recipes.map((r) => (
          <li key={r.id} className={styles.row}>
            <span className={styles.rowTitle}>{r.title}</span>
            <Stepper
              aria-label={`Multiplier for ${r.title}`}
              value={multiplierFor(r.id)}
              onChange={(v) => setMultipliers((m) => ({ ...m, [r.id]: v }))}
            />
          </li>
        ))}
      </ul>
    </Dialog>
  );
}
