import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

const THEME_KEY = "recipe.theme";
const PREFERENCES: ThemePreference[] = ["system", "light", "dark"];

interface ThemeContextValue {
  /** The user's stored choice. `"system"` follows `prefers-color-scheme`. */
  preference: ThemePreference;
  /** The theme actually in effect right now. */
  resolved: ResolvedTheme;
  setPreference: (next: ThemePreference) => void;
  /** system -> light -> dark -> system. Drives the app-shell toggle. */
  cycle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStored(): ThemePreference {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") return raw;
  } catch {
    /* storage unavailable */
  }
  return "system";
}

function prefersDark(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] =
    useState<ThemePreference>(readStored);
  const [systemDark, setSystemDark] = useState<boolean>(prefersDark);

  const resolved: ResolvedTheme =
    preference === "system" ? (systemDark ? "dark" : "light") : preference;

  // The element always carries an explicit resolved theme (tokens.css has no
  // root-level `prefers-color-scheme` block); persist the raw preference.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", resolved);
    try {
      localStorage.setItem(THEME_KEY, preference);
    } catch {
      /* storage unavailable */
    }
  }, [preference, resolved]);

  // Keep the resolved theme live while the preference is "system".
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
  }, []);

  const cycle = useCallback(() => {
    setPreferenceState((current) => {
      const idx = PREFERENCES.indexOf(current);
      return PREFERENCES[(idx + 1) % PREFERENCES.length];
    });
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, resolved, setPreference, cycle }),
    [preference, resolved, setPreference, cycle],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === null) {
    throw new Error("useTheme must be used within a <ThemeProvider>");
  }
  return ctx;
}
