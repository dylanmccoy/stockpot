import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthProvider";
import { AppRouter } from "./router";

// Phase 0 smoke: the provider stack (QueryClient + Auth + Router) mounts and the
// route table wires up. The full `renderApp` seam helper lands in Phase 3.
function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppRouter", () => {
  it("redirects an unauthenticated visitor from a guarded route to /login", async () => {
    renderAt("/inventory");
    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
  });

  it("serves the in-app NotFound page for an unknown path", async () => {
    renderAt("/no/such/place");
    expect(
      await screen.findByRole("heading", { name: "Page not found" }),
    ).toBeInTheDocument();
  });
});
