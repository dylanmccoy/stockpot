import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { useTheme, type ThemePreference } from "./theme";
import styles from "./AppShell.module.css";

const DESTINATIONS = [
  { to: "/", label: "Recipes", icon: "🍳", end: true },
  { to: "/inventory", label: "Inventory", icon: "🧺", end: false },
  { to: "/groceries", label: "Groceries", icon: "🛒", end: false },
  { to: "/history", label: "History", icon: "📖", end: false },
];

const THEME_LABEL: Record<ThemePreference, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

export function AppShell() {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  // Route change moves focus to the content region (docs/frontend/spec.md §9).
  useEffect(() => {
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

function UserMenu() {
  const { user, logout } = useAuth();
  const { preference, resolved, cycle } = useTheme();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const themeSuffix = preference === "system" ? ` (${resolved})` : "";

  return (
    <div className={styles.userMenu} ref={menuRef}>
      <button
        type="button"
        className={styles.userTrigger}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {user ? user.username : "Account"}
      </button>

      {open && (
        <div className={styles.menu} role="menu">
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={cycle}
          >
            Theme: {THEME_LABEL[preference]}
            {themeSuffix}
          </button>
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={() => {
              setOpen(false);
              void logout();
            }}
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
