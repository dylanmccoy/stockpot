import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

// Phase 0 shell: a minimal semantic frame with the four primary destinations.
// Phase 1 replaces this with the responsive top-bar / bottom-tab-bar chrome,
// the token-driven theme, and the user menu.

const DESTINATIONS = [
  { to: "/", label: "Recipes", end: true },
  { to: "/inventory", label: "Inventory", end: false },
  { to: "/groceries", label: "Groceries", end: false },
  { to: "/history", label: "History", end: false },
];

export function AppShell() {
  const { user, logout } = useAuth();

  return (
    <>
      <header>
        <strong>Recipes</strong>
        <nav aria-label="Primary">
          {DESTINATIONS.map((d) => (
            <NavLink key={d.to} to={d.to} end={d.end}>
              {d.label}
            </NavLink>
          ))}
        </nav>
        <div>
          {user ? <span>{user.username}</span> : null}
          <button type="button" onClick={() => void logout()}>
            Log out
          </button>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  );
}
