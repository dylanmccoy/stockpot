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
import type { UserRead } from "../types";
import { AuthContext, type AuthStatus, type AuthContextValue } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserRead | null>(null);
  const [status, setStatus] = useState<AuthStatus>(
    getToken() === null ? "anonymous" : "loading",
  );

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
        if (cancelled) return;
        setToken(null);
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // A 401 on any gated route means "log in again": drop the token and cache.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null);
      setUser(null);
      setStatus("anonymous");
      queryClient.clear();
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await authApi.login({ username, password });
    setToken(res.token);
    setUser(res.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // An expired token 401s before logout can run — treat that as success.
    }
    setToken(null);
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, login, logout }),
    [user, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
