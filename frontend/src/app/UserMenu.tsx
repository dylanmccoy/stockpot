import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { useTheme, type ThemePreference } from "./theme";
import styles from "./AppShell.module.css";

const THEME_LABEL: Record<ThemePreference, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

/**
 * Account disclosure in the app-shell top bar: theme cycle + logout. A plain
 * button popup driven by `aria-expanded` alone (not the ARIA menu widget, so no
 * `aria-haspopup`) — Tab reaches the items, `Esc` closes and restores focus to
 * the trigger, an outside click dismisses.
 */
export function UserMenu() {
  const { user, logout } = useAuth();
  const { preference, resolved, cycle } = useTheme();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    firstItemRef.current?.focus();

    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
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
    <div className={styles.userMenu} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.userTrigger}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {user ? user.username : "Account"}
      </button>

      {open && (
        <div className={styles.menu}>
          <button
            ref={firstItemRef}
            type="button"
            className={styles.menuItem}
            onClick={cycle}
          >
            Theme: {THEME_LABEL[preference]}
            {themeSuffix}
          </button>
          <button
            type="button"
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
