import { Link } from "react-router-dom";

/** In-app catch-all 404 (docs/frontend/spec.md §3 route table). */
export default function NotFound() {
  return (
    <main>
      <h1>Page not found</h1>
      <p>
        <Link to="/">Back to recipes</Link>
      </p>
    </main>
  );
}
