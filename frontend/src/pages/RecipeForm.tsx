// Placeholder — the real create/edit form (unified ingredient table,
// paste-to-append with preview, PUT full replace) lands in Phase 3
// (docs/frontend/spec.md §10.3).
export default function RecipeForm({ mode }: { mode: "create" | "edit" }) {
  return <h1>{mode === "create" ? "New recipe" : "Edit recipe"}</h1>;
}
