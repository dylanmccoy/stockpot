import { createContext } from "react";
import type { UserRead } from "../types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  user: UserRead | null;
  status: AuthStatus;
  /** Resolves on success; throws the normalized `ApiError` on failure. */
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
