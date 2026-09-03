import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { recipesApi } from "../api/recipes";
import type { RecipeIngredientRead, RecipeRead } from "../types";
import { ApiError, GENERIC_ERROR_MESSAGE } from "../lib/apiError";
import { formatQuantity } from "../lib/format";
import { Button, Dialog, Stepper, useToast } from "../components";
import styles from "./RecipeDetail.module.css";

// RecipeDetail — body + multiplier (spec §10.4, body Phase 3). Availability
// (Phase 4) and the cook action (Phase 5) hang off the same multiplier and land
// in later tickets; the made-history panel below is a placeholder for ticket 11.

/** `source_url` is stored verbatim and never validated (R-14); this only decides
 *  whether to offer an "open link" affordance. Mirrors `asOpenableUrl` in
 *  RecipeForm — a few lines, kept local rather than importing across pages. */
export function asOpenableUrl(raw: string | null): string | null {
  const t = raw?.trim();
  if (!t) return null;
  try {
    const url = new URL(t);
    return url.protocol === "http:" || url.protocol === "https:"
      ? url.href
      : null;
  } catch {
    return null;
  }
}

/** Count units carry no unit word — the label is just the number (spec §7.2). */
const COUNT_UNITS: ReadonlySet<string | null> = new Set([null, "unit", "each"]);

/** A recipe row's quantity, scaled by the multiplier and run through
 *  `formatQuantity` (spec §7.2), with its unit appended — never a raw float.
 *  `null` quantity (to-taste) → `""`; the caller renders "to taste" itself. */
export function scaledQuantityLabel(
  ingredient: Pick<RecipeIngredientRead, "quantity" | "unit">,
  multiplier: number,
): string {
  const { quantity, unit } = ingredient;
  if (quantity === null) return "";
  const formatted = formatQuantity(quantity * multiplier, unit);
  if (COUNT_UNITS.has(unit)) return formatted;
  return [formatted, unit].filter(Boolean).join(" ");
}

function NotFoundPanel() {
  return (
    <section className={styles.panel} role="alert">
      <h1>Recipe not found</h1>
      <p className={styles.muted}>This recipe may have been deleted.</p>
      <Link to="/">Back to recipes</Link>
    </section>
  );
}

export default function RecipeDetail() {
  const { id } = useParams();
  const numeric = Number(id);
  if (!id || !Number.isInteger(numeric) || numeric <= 0) {
    return <NotFoundPanel />;
  }
  // Remount on id change so the multiplier resets to 1 on every visit to the
  // screen (spec §10.4 — a stale remembered multiplier is a footgun).
  return <RecipeDetailView key={id} id={numeric} />;
}

function RecipeDetailView({ id }: { id: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [multiplier, setMultiplier] = useState(1);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // One query per screen; request cancellation buys nothing here, so the
  // adapter's optional `signal` is left unused (matches RecipeList).
  const query = useQuery({
    queryKey: ["recipe", id],
    queryFn: () => recipesApi.get(id),
  });

  const del = useMutation({
    mutationFn: () => recipesApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate("/");
    },
    onError: () => {
      setConfirmOpen(false);
      toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
    },
  });

  if (query.isPending) {
    return (
      <section className={styles.page} aria-busy="true">
        <p role="status" className="sr-only">
          Loading recipe…
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
            : "Could not load this recipe."}
        </p>
        <Button variant="secondary" onClick={() => query.refetch()}>
          Retry
        </Button>
      </section>
    );
  }

  const recipe: RecipeRead = query.data;
  const openUrl = asOpenableUrl(recipe.source_url);
  // The API returns ingredients ordered by position; sort defensively so the
  // screen still reads top-to-bottom if that ever slips (ticket: "in order").
  const ingredients = [...recipe.ingredients].sort(
    (a, b) => a.position - b.position,
  );

  const meta: Array<[string, string]> = [];
  if (recipe.cuisine) meta.push(["Cuisine", recipe.cuisine]);
  if (recipe.servings != null) meta.push(["Servings", String(recipe.servings)]);
  if (recipe.prep_time != null) meta.push(["Prep", `${recipe.prep_time} min`]);
  if (recipe.cook_time != null) meta.push(["Cook", `${recipe.cook_time} min`]);

  return (
    <section className={styles.page}>
      <header className={styles.head}>
        <h1>{recipe.title}</h1>
        <Button variant="danger" onClick={() => setConfirmOpen(true)}>
          Delete recipe
        </Button>
      </header>

      {meta.length > 0 && (
        <dl className={styles.meta}>
          {meta.map(([term, value]) => (
            <div key={term} className={styles.metaItem}>
              <dt>{term}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {recipe.source_url && (
        <p className={styles.source}>
          {openUrl ? (
            <a href={openUrl} target="_blank" rel="noreferrer">
              Open source link
            </a>
          ) : (
            <span>Source: {recipe.source_url}</span>
          )}
        </p>
      )}

      <section className={styles.section} aria-labelledby="ingredients-heading">
        <div className={styles.sectionHead}>
          <h2 id="ingredients-heading">Ingredients</h2>
          <Stepper
            label="Multiplier"
            value={multiplier}
            onChange={setMultiplier}
          />
        </div>
        <ul className={styles.ingredients}>
          {ingredients.map((ing) => {
            const qty = scaledQuantityLabel(ing, multiplier);
            const note = ing.note?.trim();
            return (
              <li key={ing.id} className={styles.ingredient}>
                {qty && <span className={styles.qty}>{qty}</span>}
                <span className={styles.item}>{ing.item}</span>
                {ing.quantity === null && (
                  <span className={styles.note}>to taste</span>
                )}
                {note && note.toLowerCase() !== "to taste" && (
                  <span className={styles.note}>{note}</span>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {recipe.steps.length > 0 && (
        <section className={styles.section} aria-labelledby="steps-heading">
          <h2 id="steps-heading">Steps</h2>
          <ol className={styles.steps}>
            {recipe.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </section>
      )}

      {recipe.notes.trim() && (
        <section className={styles.section} aria-labelledby="notes-heading">
          <h2 id="notes-heading">Notes</h2>
          <p className={styles.notes}>{recipe.notes}</p>
        </section>
      )}

      {/* Per-recipe made-history panel — filled in ticket 11 (spec §10.8). */}
      <section className={styles.section} aria-labelledby="history-heading">
        <h2 id="history-heading">Made history</h2>
        <p className={styles.muted}>Cook this recipe to start its history.</p>
      </section>

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Delete this recipe?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={del.isPending}
              onClick={() => del.mutate()}
            >
              Delete
            </Button>
          </>
        }
      >
        <p>
          “{recipe.title}” will be permanently removed. This can’t be undone.
        </p>
      </Dialog>
    </section>
  );
}
