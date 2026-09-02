import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/server";
import { errorHandlers } from "../test/errorHandlers";
import { makeQueryClient } from "../test/helpers";
import { getToken } from "../api/client";
import { ToastProvider } from "../components";
import { AuthProvider } from "../auth/AuthProvider";
import Login from "./Login";

function renderLogin(path = "/login") {
  const queryClient = makeQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/" element={<h1>Recipes</h1>} />
              <Route path="/inventory" element={<h1>Inventory</h1>} />
            </Routes>
          </AuthProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

function registerSection() {
  return screen
    .getByRole("heading", { name: "Create an account" })
    .closest("section") as HTMLElement;
}

async function fillLogin(username = "cook", password = "pw") {
  await userEvent.type(screen.getByLabelText("Username"), username);
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
}

async function fillRegister(username = "newcook", password = "password1") {
  const form = registerSection();
  await userEvent.type(within(form).getByLabelText("Username"), username);
  await userEvent.type(within(form).getByLabelText("Password"), password);
  await userEvent.click(
    within(form).getByRole("button", { name: "Create account" }),
  );
  return form;
}

afterEach(() => vi.unstubAllEnvs());

describe("Login", () => {
  it("renders the login form", () => {
    renderLogin();
    expect(
      screen.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("on success redirects to the ?next path", async () => {
    renderLogin("/login?next=/inventory");
    await fillLogin();
    expect(
      await screen.findByRole("heading", { name: "Inventory" }),
    ).toBeInTheDocument();
    expect(getToken()).toBe("test-token");
  });

  it("on success with no ?next redirects home", async () => {
    renderLogin();
    await fillLogin();
    expect(
      await screen.findByRole("heading", { name: "Recipes" }),
    ).toBeInTheDocument();
  });

  it("ignores an off-origin ?next and redirects home", async () => {
    renderLogin("/login?next=https://evil.example/phish");
    await fillLogin();
    expect(
      await screen.findByRole("heading", { name: "Recipes" }),
    ).toBeInTheDocument();
  });

  it("ignores a protocol-relative ?next and redirects home", async () => {
    renderLogin("/login?next=//evil.example");
    await fillLogin();
    expect(
      await screen.findByRole("heading", { name: "Recipes" }),
    ).toBeInTheDocument();
  });

  it("shows the 401 message inline and stays on the page", async () => {
    server.use(errorHandlers.invalidLogin());
    renderLogin("/login?next=/inventory");
    await fillLogin("cook", "wrong");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid username or password",
    );
    expect(
      screen.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it("sends an unexpected failure to a toast, not the inline banner", async () => {
    server.use(errorHandlers.serverError("post", "/api/auth/login"));
    renderLogin();
    await fillLogin();
    const region = screen.getByRole("region", { name: "Notifications" });
    expect(
      await within(region).findByText("Something went wrong. Try again."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not render the register form by default", () => {
    renderLogin();
    expect(
      screen.queryByRole("heading", { name: "Create an account" }),
    ).not.toBeInTheDocument();
  });

  describe("with VITE_ENABLE_REGISTER set", () => {
    it("renders the register form", () => {
      vi.stubEnv("VITE_ENABLE_REGISTER", "1");
      renderLogin();
      expect(
        screen.getByRole("heading", { name: "Create an account" }),
      ).toBeInTheDocument();
    });

    it("stays hidden for a non opt-in flag value", () => {
      vi.stubEnv("VITE_ENABLE_REGISTER", "false");
      renderLogin();
      expect(
        screen.queryByRole("heading", { name: "Create an account" }),
      ).not.toBeInTheDocument();
    });

    it("surfaces a 403 registration refusal on a form banner", async () => {
      vi.stubEnv("VITE_ENABLE_REGISTER", "1");
      server.use(errorHandlers.registrationDisabled());
      renderLogin();
      const form = await fillRegister();
      expect(await within(form).findByRole("alert")).toHaveTextContent(
        "registration disabled",
      );
    });

    it("surfaces a 403 invalid-code rejection on a form banner", async () => {
      vi.stubEnv("VITE_ENABLE_REGISTER", "1");
      server.use(errorHandlers.invalidRegistrationCode());
      renderLogin();
      const form = await fillRegister();
      expect(await within(form).findByRole("alert")).toHaveTextContent(
        "invalid registration code",
      );
    });

    it("surfaces a 409 username-taken on the username field", async () => {
      vi.stubEnv("VITE_ENABLE_REGISTER", "1");
      server.use(errorHandlers.usernameTaken());
      renderLogin();
      const form = await fillRegister("taken");
      const username = within(form).getByLabelText("Username");
      await waitFor(() =>
        expect(username).toHaveAttribute("aria-invalid", "true"),
      );
      expect(within(form).getByText("username taken")).toBeInTheDocument();
    });

    it("sends an unexpected registration failure to a toast", async () => {
      vi.stubEnv("VITE_ENABLE_REGISTER", "1");
      server.use(errorHandlers.serverError("post", "/api/auth/register"));
      renderLogin();
      const form = await fillRegister();
      const region = screen.getByRole("region", { name: "Notifications" });
      expect(
        await within(region).findByText("Something went wrong. Try again."),
      ).toBeInTheDocument();
      expect(within(form).queryByRole("alert")).not.toBeInTheDocument();
    });

    it("signs in and redirects on a successful registration", async () => {
      vi.stubEnv("VITE_ENABLE_REGISTER", "1");
      renderLogin("/login?next=/inventory");
      await fillRegister();
      expect(
        await screen.findByRole("heading", { name: "Inventory" }),
      ).toBeInTheDocument();
    });
  });
});
