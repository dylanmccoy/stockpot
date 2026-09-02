import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "./theme";

function Probe() {
  const { preference, resolved, cycle, setPreference } = useTheme();
  return (
    <>
      <output data-testid="pref">{preference}</output>
      <output data-testid="resolved">{resolved}</output>
      <button type="button" onClick={cycle}>
        cycle
      </button>
      <button type="button" onClick={() => setPreference("dark")}>
        force dark
      </button>
    </>
  );
}

function renderProbe() {
  return render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  );
}

beforeEach(() => {
  document.documentElement.removeAttribute("data-theme");
});
afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeProvider", () => {
  it("defaults to system, resolving to light when nothing is stored (jsdom has no matchMedia)", () => {
    renderProbe();
    expect(screen.getByTestId("pref")).toHaveTextContent("system");
    expect(screen.getByTestId("resolved")).toHaveTextContent("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem("recipe.theme")).toBe("system");
  });

  it("reads a stored override and reflects it on <html>", () => {
    localStorage.setItem("recipe.theme", "dark");
    renderProbe();
    expect(screen.getByTestId("pref")).toHaveTextContent("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("cycles system -> light -> dark -> system and persists the raw preference", async () => {
    renderProbe();
    const cycle = screen.getByRole("button", { name: "cycle" });

    await userEvent.click(cycle);
    expect(screen.getByTestId("pref")).toHaveTextContent("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem("recipe.theme")).toBe("light");

    await userEvent.click(cycle);
    expect(screen.getByTestId("pref")).toHaveTextContent("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("recipe.theme")).toBe("dark");

    await userEvent.click(cycle);
    expect(screen.getByTestId("pref")).toHaveTextContent("system");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem("recipe.theme")).toBe("system");
  });

  it("setPreference forces a concrete theme", async () => {
    renderProbe();
    await userEvent.click(screen.getByRole("button", { name: "force dark" }));
    expect(screen.getByTestId("resolved")).toHaveTextContent("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("throws when useTheme is called outside the provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/ThemeProvider/);
    spy.mockRestore();
  });
});
