import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { recipesApi } from "../api/recipes";
import type { RecipeRead } from "../types";
import { Badge, Button, Card, Field, Input, Select } from "../components";
import { cx } from "../lib/cx";
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

/** Returns a new array; "newest" keeps the server order (`created_at DESC, id DESC`). */
export function sortRecipes(
  recipes: RecipeRead[],
  mode: SortMode,
): RecipeRead[] {
  const copy = [...recipes];
  if (mode === "title") {
    return copy.sort((a, b) =>
      a.title.localeCompare(b.title, undefined, { sensitivity: "base" }),
    );
  }
  if (mode === "updated") {
    return copy.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }
  return copy;
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) =>
    a.localeCompare(b, undefined, { sensitivity: "base" }),
  );
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

function RecipeCard({ recipe }: { recipe: RecipeRead }) {
  const time = timeSummary(recipe);
  const count = recipe.ingredients.length;
  return (
    <Link to={`/recipes/${recipe.id}`} className={styles.cardLink}>
      <Card className={styles.card}>
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

  const recipes = useMemo(() => data ?? [], [data]);

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
        <Link to="/recipes/new" className={cx(styles.cta, styles.ctaPrimary)}>
          Add recipe
        </Link>
      </header>

      {status === "pending" && (
        <p role="status" className={styles.status}>
          Loading recipes…
        </p>
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
          <p>No recipes yet — add your first recipe.</p>
          <Link to="/recipes/new" className={cx(styles.cta, styles.ctaPrimary)}>
            Add your first recipe
          </Link>
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
            <p className={styles.noMatch}>No recipes match your search.</p>
          ) : (
            <ul className={styles.grid}>
              {visible.map((recipe) => (
                <li key={recipe.id}>
                  <RecipeCard recipe={recipe} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
