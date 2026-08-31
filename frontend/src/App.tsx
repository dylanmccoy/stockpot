import { useEffect, useState } from "react";
import { api } from "./api";
import type { Recipe, RecipeInput } from "./types";

const EMPTY: RecipeInput = { title: "", ingredients: "", instructions: "" };

export default function App() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [draft, setDraft] = useState<RecipeInput>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => api.list().then(setRecipes).catch((e) => setError(String(e)));

  useEffect(() => {
    refresh();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.create(draft);
      setDraft(EMPTY);
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <main style={{ maxWidth: 640, margin: "2rem auto", fontFamily: "system-ui" }}>
      <h1>Recipes</h1>
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <form onSubmit={submit} style={{ display: "grid", gap: 8, marginBottom: 24 }}>
        <input
          placeholder="Title"
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          required
        />
        <textarea
          placeholder="Ingredients"
          value={draft.ingredients}
          onChange={(e) => setDraft({ ...draft, ingredients: e.target.value })}
        />
        <textarea
          placeholder="Instructions"
          value={draft.instructions}
          onChange={(e) => setDraft({ ...draft, instructions: e.target.value })}
        />
        <button type="submit">Add recipe</button>
      </form>

      <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 12 }}>
        {recipes.map((r) => (
          <li key={r.id} style={{ border: "1px solid #ccc", borderRadius: 8, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <strong>{r.title}</strong>
              <button onClick={() => api.remove(r.id).then(refresh)}>Delete</button>
            </div>
            {r.ingredients && <p style={{ whiteSpace: "pre-wrap" }}>{r.ingredients}</p>}
            {r.instructions && <p style={{ whiteSpace: "pre-wrap" }}>{r.instructions}</p>}
          </li>
        ))}
      </ul>
    </main>
  );
}
