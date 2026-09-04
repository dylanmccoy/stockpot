import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { recipesApi } from "../api/recipes";
import type { GroceryListRead, RecipeRead } from "../types";
import {
  Badge,
  Button,
  Card,
  Field,
  Input,
  Select,
  useToast,
} from "../components";
import { cx } from "../lib/cx";
import { GroceryCreateDialog } from "./GroceryCreateDialog";
import styles from "./RecipeList.module.css";

export type SortMode = "newest" | "title" | "updated";

export interface Facets {
  cuisines: string[];
  tags: string[];
}

/** Free-text match over title + cuisine + tag text (case-insensitive substring). */
export function searchRecipes(
  recipes: RecipeRead[],
  query: string,
): RecipeRead[] {
  const q = query.trim().toLowerCase();
  if (!q) return recipes;
  return recipes.filter((r) => {
    const haystack = [r.title, r.cuisine ?? "", ...r.tags]
      .join("\n")
      .toLowerCase();
    return haystack.includes(q);
  });
}

/** Union within a facet, intersection across facets (spec §10.2). */
export function filterByFacets(
  recipes: RecipeRead[],
  facets: Facets,
): RecipeRead[] {
  const { cuisines, tags } = facets;
  return recipes.filter((r) => {
    if (cuisines.length && !(r.cuisine && cuisines.includes(r.cuisine))) {
      return false;
    }
    if (tags.length && !r.tags.some((t) => tags.includes(t))) {
      return false;
    }
    return true;
  });
}

/** Case-insensitive string order. */
function ciCompare(a: string, b: string): number {
  return a.localeCompare(b, undefined, { sensitivity: "base" });
}

/** Returns a new array; "newest" keeps the server order (`created_at DESC, id DESC`). */
export function sortRecipes(
  recipes: RecipeRead[],
  mode: SortMode,
): RecipeRead[] {
  const copy = [...recipes];
  if (mode === "title") {
    return copy.sort((a, b) => ciCompare(a.title, b.title));
  }
  if (mode === "updated") {
    return copy.sort(
      (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
    );
  }
  return copy;
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort(ciCompare);
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value)
    ? list.filter((v) => v !== value)
    : [...list, value];
}

function timeSummary(recipe: RecipeRead): string | null {
  const parts: string[] = [];
  if (recipe.prep_time != null) parts.push(`${recipe.prep_time} min prep`);
  if (recipe.cook_time != null) parts.push(`${recipe.cook_time} min cook`);
  return parts.length ? parts.join(" · ") : null;
}

function FacetGroup({
  legend,
  options,
  selected,
  onToggle,
}: {
  legend: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  if (!options.length) return null;
  return (
    <fieldset className={styles.facet}>
      <legend className={styles.facetLegend}>{legend}</legend>
      <div className={styles.facetOptions}>
        {options.map((option) => (
          <label key={option} className={styles.facetOption}>
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => onToggle(option)}
            />
            {option}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** A `<Link>` to the create form, styled as the primary action. */
function CtaLink({ children }: { children: ReactNode }) {
  return (
    <Link to="/recipes/new" className={cx(styles.cta, styles.ctaPrimary)}>
      {children}
    </Link>
  );
}

function RecipeCard({
  recipe,
  selectMode,
  checked,
  onToggle,
}: {
  recipe: RecipeRead;
  selectMode: boolean;
  checked: boolean;
  onToggle: (id: number) => void;
}) {
  const time = timeSummary(recipe);
  const count = recipe.ingredients.length;
  const cardBody = (
    <Card className={cx(styles.card, checked && styles.cardChecked)}>
      <h2 className={styles.cardTitle}>{recipe.title}</h2>
      {recipe.cuisine && <p className={styles.cuisine}>{recipe.cuisine}</p>}
      {recipe.tags.length > 0 && (
        <p className={styles.tags}>
          {recipe.tags.map((tag) => (
            <Badge key={tag}>{tag}</Badge>
          ))}
        </p>
      )}
      <p className={styles.meta}>
        {time && <span>{time}</span>}
        <span>
          {count} ingredient{count === 1 ? "" : "s"}
        </span>
      </p>
    </Card>
  );

  if (selectMode) {
    return (
      <label className={cx(styles.cardShell, styles.cardSelect)}>
        <input
          type="checkbox"
          className={styles.cardCheckbox}
          aria-label={recipe.title}
          checked={checked}
          onChange={() => onToggle(recipe.id)}
        />
        {cardBody}
      </label>
    );
  }

  return (
    <Link
      to={`/recipes/${recipe.id}`}
      className={cx(styles.cardShell, styles.cardLink)}
    >
      {cardBody}
    </Link>
  );
}

export default function RecipeList() {
  // One paramless query for the whole screen; request cancellation buys nothing
  // here, so the adapter's optional `signal` is left unused.
  const { data, status, error, refetch, isFetching } = useQuery({
    queryKey: ["recipes"],
    queryFn: () => recipesApi.list(),
  });

  const [query, setQuery] = useState("");
  const [cuisines, setCuisines] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [sort, setSort] = useState<SortMode>("newest");

  // Multi-select "gather" mode: pick several recipes, then turn them into a
  // grocery list. Leaving the mode drops the selection.
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [dialogOpen, setDialogOpen] = useState(false);

  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();

  function toggleSelectMode() {
    if (selectMode) setSelected(new Set());
    setSelectMode((on) => !on);
  }

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function deselect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  function handleCreated(list: GroceryListRead) {
    // spec §10.5: a new list makes the /groceries index (ticket 12b) stale.
    queryClient.invalidateQueries({ queryKey: ["grocery"] });
    toast.show("Grocery list created.", { variant: "success" });
    setDialogOpen(false);
    setSelected(new Set());
    setSelectMode(false);
    navigate(`/groceries/${list.id}`);
  }

  const recipes = useMemo(() => data ?? [], [data]);

  // The dialog operates on the selected recipes that still exist in the list —
  // a refetch after the R-13 recovery path shrinks this, and an emptied
  // selection closes the dialog.
  const selectedRecipes = useMemo(
    () => recipes.filter((r) => selected.has(r.id)),
    [recipes, selected],
  );

  useEffect(() => {
    if (dialogOpen && selectedRecipes.length === 0) setDialogOpen(false);
  }, [dialogOpen, selectedRecipes.length]);

  const cuisineOptions = useMemo(
    () =>
      uniqueSorted(
        recipes.map((r) => r.cuisine).filter((c): c is string => !!c),
      ),
    [recipes],
  );
  const tagOptions = useMemo(
    () => uniqueSorted(recipes.flatMap((r) => r.tags)),
    [recipes],
  );

  const visible = useMemo(
    () =>
      sortRecipes(
        filterByFacets(searchRecipes(recipes, query), { cuisines, tags }),
        sort,
      ),
    [recipes, query, cuisines, tags, sort],
  );

  return (
    <section className={styles.page} aria-busy={isFetching || undefined}>
      <header className={styles.head}>
        <h1>Recipes</h1>
        <div className={styles.headActions}>
          {status === "success" && recipes.length > 0 && (
            <Button
              variant="secondary"
              aria-pressed={selectMode}
              onClick={toggleSelectMode}
            >
              {selectMode ? "Done" : "Select"}
            </Button>
          )}
          <CtaLink>Add recipe</CtaLink>
        </div>
      </header>

      {status === "pending" && (
        <>
          <p role="status" className="sr-only">
            Loading recipes…
          </p>
          <ul className={styles.grid} aria-hidden="true">
            {Array.from({ length: 6 }, (_, i) => (
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
            {error instanceof Error ? error.message : "Could not load recipes."}
          </p>
          <Button variant="secondary" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}

      {status === "success" && recipes.length === 0 && (
        <div className={styles.empty}>
          <p>No recipes yet.</p>
          <CtaLink>Add your first recipe</CtaLink>
        </div>
      )}

      {status === "success" && recipes.length > 0 && (
        <>
          <div className={styles.controls}>
            <Field label="Search recipes">
              <Input
                type="search"
                placeholder="title, cuisine, or tag"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </Field>
            <Field label="Sort">
              <Select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortMode)}
              >
                <option value="newest">Newest</option>
                <option value="title">Title A–Z</option>
                <option value="updated">Recently updated</option>
              </Select>
            </Field>
          </div>

          {(cuisineOptions.length > 0 || tagOptions.length > 0) && (
            <div className={styles.facets}>
              <FacetGroup
                legend="Cuisine"
                options={cuisineOptions}
                selected={cuisines}
                onToggle={(v) => setCuisines((prev) => toggle(prev, v))}
              />
              <FacetGroup
                legend="Tags"
                options={tagOptions}
                selected={tags}
                onToggle={(v) => setTags((prev) => toggle(prev, v))}
              />
            </div>
          )}

          {visible.length === 0 ? (
            <p className={styles.noMatch}>
              No recipes match your search or filters.
            </p>
          ) : (
            <ul className={styles.grid}>
              {visible.map((recipe) => (
                <li key={recipe.id}>
                  <RecipeCard
                    recipe={recipe}
                    selectMode={selectMode}
                    checked={selected.has(recipe.id)}
                    onToggle={toggleSelected}
                  />
                </li>
              ))}
            </ul>
          )}

          <p className="sr-only" role="status">
            {selected.size > 0 ? `${selected.size} selected` : ""}
          </p>
          {selected.size > 0 && (
            <div className={styles.actionBar}>
              <span aria-hidden="true">{selected.size} selected</span>
              <Button onClick={() => setDialogOpen(true)}>
                Create grocery list
              </Button>
            </div>
          )}

          <GroceryCreateDialog
            open={dialogOpen}
            recipes={selectedRecipes}
            onClose={() => setDialogOpen(false)}
            onDrop={deselect}
            onCreated={handleCreated}
          />
        </>
      )}
    </section>
  );
}
