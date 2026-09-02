import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { getToken, setToken } from "../api/client";
import { AuthProvider } from "../auth/AuthProvider";
import { ThemeProvider } from "./theme";
import { AppRouter } from "./router";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="loc">{location.pathname + location.search}</div>;
}

function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ThemeProvider>
          <AuthProvider>
            <LocationProbe />
            <AppRouter />
          </AuthProvider>
        </ThemeProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

const loc = () => screen.getByTestId("loc").textContent;
const unauthorized = () =>
  HttpResponse.json({ detail: "not authenticated" }, { status: 401 });

describe("auth flow", () => {
  it("sends an anonymous visitor from a guarded route to /login?next=", async () => {
    renderApp("/inventory");
    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(loc()).toBe("/login?next=%2Finventory");
  });

  // The backend maps missing / malformed / wrong-scheme / unknown / expired
  // tokens all to `401 {"detail":"not authenticated"}` (docs/spec.md §
  // get_current_user), so to the client the five are one response. Each must
  // land the user back on /login with their target preserved.
  it.each(["missing", "malformed", "wrong scheme", "unknown token", "expired"])(
    "redirects to login when /me 401s (%s token)",
    async (_shape) => {
      setToken("some-token");
      server.use(http.get("/api/auth/me", unauthorized));

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
    server.use(http.get("/api/auth/me", unauthorized));

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
    queryClient.setQueryData(["recipes"], ["cached"]);

    await userEvent.click(screen.getByRole("button", { name: "cook" }));
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(getToken()).toBeNull();
    expect(queryClient.getQueryData(["recipes"])).toBeUndefined();
  });
});
