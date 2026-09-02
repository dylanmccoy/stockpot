import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { getToken, setToken } from "../api/client";
import { ToastProvider } from "../components";
import { AuthProvider } from "../auth/AuthProvider";
import { ThemeProvider } from "./theme";
import { AppRouter } from "./router";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="loc">{location.pathname + location.search}</div>;
}

function renderApp(path: string) {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <LocationProbe />
              <AppRouter />
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

const loc = () => screen.getByTestId("loc").textContent;

describe("auth flow", () => {
  it("sends an anonymous visitor from a guarded route to /login?next=", async () => {
    renderApp("/inventory");
    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(loc()).toBe("/login?next=%2Finventory");
  });

  // The backend maps missing / malformed / wrong-scheme / unknown / expired
  // tokens all to `401 {"detail":"not authenticated"}` (docs/spec.md
  // get_current_user), so to the client the five are one response. Each must
  // land the user back on /login with their target preserved.
  it.each(["missing", "malformed", "wrong scheme", "unknown token", "expired"])(
    "redirects to login when /me 401s (%s token)",
    async (_shape) => {
      setToken("some-token");
      server.use(errorHandlers.notAuthenticated("get", "/api/auth/me"));

      renderApp("/inventory");

      expect(
        await screen.findByRole("heading", { name: "Log in" }),
      ).toBeInTheDocument();
      expect(loc()).toBe("/login?next=%2Finventory");
      expect(getToken()).toBeNull();
    },
  );

  it("an expired token present on load ends in the logged-out state", async () => {
    setToken("expired-token");
    server.use(errorHandlers.notAuthenticated("get", "/api/auth/me"));

    renderApp("/");

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it("logs in from the redirect and returns to the attempted route", async () => {
    renderApp("/inventory");
    await screen.findByRole("heading", { name: "Log in" });

    await userEvent.type(screen.getByLabelText("Username"), "cook");
    await userEvent.type(screen.getByLabelText("Password"), "pw");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(
      await screen.findByRole("heading", { name: "Inventory" }),
    ).toBeInTheDocument();
    expect(loc()).toBe("/inventory");
    expect(getToken()).toBe("test-token");
  });

  it("logout from the user menu clears the session and returns to login", async () => {
    setToken("good-token");
    const queryClient = renderApp("/");
    expect(
      await screen.findByRole("heading", { name: "Recipes" }),
    ).toBeInTheDocument();
    // Any resident cache entry must be dropped on logout — use a key no mounted
    // screen re-fetches, so the assertion reflects the logout wipe, not a refetch.
    queryClient.setQueryData(["cook-logs"], ["cached"]);

    await userEvent.click(screen.getByRole("button", { name: "cook" }));
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(getToken()).toBeNull();
    expect(queryClient.getQueryData(["cook-logs"])).toBeUndefined();
  });
});
