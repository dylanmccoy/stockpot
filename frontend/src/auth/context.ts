import { createContext } from "react";
import type { UserRead } from "../types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  user: UserRead | null;
  status: AuthStatus;
  /** Resolves on success; throws the normalized `ApiError` on failure. */
  login: (username: string, password: string) => Promise<void>;
  /**
   * Behind `VITE_ENABLE_REGISTER` (spec §4). Resolves on success — the new user
   * is signed in — and throws the normalized `ApiError` on failure.
   */
  register: (
    username: string,
    password: string,
    code?: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
