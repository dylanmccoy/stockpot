import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

/**
 * Guards every non-`/login` route. While the stored token is being verified we
 * hold (a real loading skeleton lands in Phase 1); an anonymous user is sent to
 * `/login?next=<attempted path>` so login can return them to their place.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <div role="status">Checking your session…</div>;
  }

  if (status === "anonymous") {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  return <>{children}</>;
}
