import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthContext, type AuthContextValue } from "../auth/context";
import { ThemeProvider } from "./theme";
import { AppShell } from "./AppShell";

function renderShell(
  overrides: Partial<AuthContextValue> = {},
  initialPath = "/",
) {
  const auth: AuthContextValue = {
    user: { id: 1, username: "dylan", created_at: "2026-01-01T00:00:00Z" },
    status: "authenticated",
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ThemeProvider>
        <AuthContext.Provider value={auth}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<h1>Recipes</h1>} />
              <Route path="/inventory" element={<h1>Inventory</h1>} />
            </Route>
          </Routes>
        </AuthContext.Provider>
      </ThemeProvider>
    </MemoryRouter>,
  );
  return auth;
}

describe("AppShell", () => {
  it("renders the four primary destinations", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const links = within(nav).getAllByRole("link");
    expect(links).toHaveLength(4);
    for (const name of ["Recipes", "Inventory", "Groceries", "History"]) {
      expect(within(nav).getByRole("link", { name })).toHaveAttribute("href");
    }
  });

  it("marks the active destination with aria-current=page", () => {
    renderShell({}, "/inventory");
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(
      within(nav).getByRole("link", { name: "Inventory" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      within(nav).getByRole("link", { name: "Recipes" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("gives the content region a focusable <main> landmark", () => {
    renderShell();
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main");
    expect(main).toHaveAttribute("tabindex", "-1");
  });

  it("shows the username and opens the user menu", async () => {
    renderShell();
    const trigger = screen.getByRole("button", { name: "dylan" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  it("cycles the theme from the user menu", async () => {
    renderShell();
    await userEvent.click(screen.getByRole("button", { name: "dylan" }));
    const themeItem = screen.getByRole("menuitem", { name: /^Theme:/ });
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    await userEvent.click(themeItem);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    document.documentElement.removeAttribute("data-theme");
  });

  it("logs out from the user menu", async () => {
    const auth = renderShell();
    await userEvent.click(screen.getByRole("button", { name: "dylan" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Log out" }));
    expect(auth.logout).toHaveBeenCalledOnce();
  });

  it("closes the menu on Escape", async () => {
    renderShell();
    const trigger = screen.getByRole("button", { name: "dylan" });
    await userEvent.click(trigger);
    await userEvent.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
