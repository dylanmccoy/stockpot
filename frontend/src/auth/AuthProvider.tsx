import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi } from "../api/auth";
import { getToken, setToken, setUnauthorizedHandler } from "../api/client";
import type { TokenResponse, UserRead } from "../types";
import { AuthContext, type AuthStatus, type AuthContextValue } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserRead | null>(null);
  const [status, setStatus] = useState<AuthStatus>(
    getToken() === null ? "anonymous" : "loading",
  );

  const adoptSession = useCallback((res: TokenResponse) => {
    setToken(res.token);
    setUser(res.user);
    setStatus("authenticated");
  }, []);

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  // Hydrate the current user from a stored token on first load.
  useEffect(() => {
    if (getToken() === null) return;
    let cancelled = false;
    authApi
      .me()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!cancelled) clearSession();
      });
    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  // A 401 on any gated route means "log in again": drop the token and cache.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession();
      queryClient.clear();
    });
    return () => setUnauthorizedHandler(null);
  }, [clearSession, queryClient]);

  const login = useCallback(
    async (username: string, password: string) => {
      adoptSession(await authApi.login({ username, password }));
    },
    [adoptSession],
  );

  const register = useCallback(
    async (username: string, password: string, code?: string) => {
      adoptSession(
        await authApi.register({
          username,
          password,
          ...(code ? { code } : {}),
        }),
      );
    },
    [adoptSession],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // An expired token 401s before logout can run — treat that as success.
    }
    clearSession();
    queryClient.clear();
  }, [clearSession, queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, login, register, logout }),
    [user, status, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
