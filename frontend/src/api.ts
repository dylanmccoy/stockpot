import type { Recipe, RecipeInput } from "./types";

const BASE = "/api/recipes";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  list: () => fetch(BASE).then((r) => json<Recipe[]>(r)),
  create: (input: RecipeInput) =>
    fetch(BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }).then((r) => json<Recipe>(r)),
  remove: (id: number) => fetch(`${BASE}/${id}`, { method: "DELETE" }).then((r) => json<void>(r)),
};
