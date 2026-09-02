import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { UserMenu } from "./UserMenu";
import styles from "./AppShell.module.css";

const DESTINATIONS = [
  { to: "/", label: "Recipes", icon: "🍳", end: true },
  { to: "/inventory", label: "Inventory", icon: "🧺", end: false },
  { to: "/groceries", label: "Groceries", icon: "🛒", end: false },
  { to: "/history", label: "History", icon: "📖", end: false },
];

export function AppShell() {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const firstRender = useRef(true);

  // Route change (not the cold load) moves focus to the content region
  // (docs/frontend/spec.md §9).
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [location.pathname]);

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <NavLink to="/" className={styles.brand} end>
          Recipes
        </NavLink>

        <nav className={styles.nav} aria-label="Primary">
          <ul>
            {DESTINATIONS.map((d) => (
              <li key={d.to}>
                <NavLink to={d.to} end={d.end} className={styles.navlink}>
                  <span className={styles.navIcon} aria-hidden="true">
                    {d.icon}
                  </span>
                  <span>{d.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <span className={styles.spacer} />
        <UserMenu />
      </header>

      <main id="main" ref={mainRef} tabIndex={-1} className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
