import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { getToken, setToken } from "../api/client";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";

function Probe() {
  const { status, user, login, register, logout } = useAuth();
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="user">{user?.username ?? "none"}</p>
      <button onClick={() => void login("cook", "pw").catch(() => {})}>
        login
      </button>
      <button
        onClick={() => void register("cook", "password1").catch(() => {})}
      >
        register
      </button>
      <button onClick={() => void logout()}>logout</button>
    </div>
  );
}

function renderAuth() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

const status = () => screen.getByTestId("status").textContent;

describe("AuthProvider", () => {
  it("is anonymous with no stored token and never calls /me", () => {
    renderAuth();
    expect(status()).toBe("anonymous");
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });

  it("login stores the token and hydrates the user", async () => {
    renderAuth();
    await userEvent.click(screen.getByRole("button", { name: "login" }));
    await waitFor(() => expect(status()).toBe("authenticated"));
    expect(screen.getByTestId("user")).toHaveTextContent("cook");
    expect(getToken()).toBe("test-token");
  });

  it("register signs the new user in", async () => {
    renderAuth();
    await userEvent.click(screen.getByRole("button", { name: "register" }));
    await waitFor(() => expect(status()).toBe("authenticated"));
    expect(getToken()).toBe("test-token");
  });

  it("logout posts logout, clears the token and drops the query cache", async () => {
    const queryClient = renderAuth();
    await userEvent.click(screen.getByRole("button", { name: "login" }));
    await waitFor(() => expect(status()).toBe("authenticated"));
    queryClient.setQueryData(["recipes"], ["cached"]);

    await userEvent.click(screen.getByRole("button", { name: "logout" }));

    await waitFor(() => expect(status()).toBe("anonymous"));
    expect(getToken()).toBeNull();
    expect(queryClient.getQueryData(["recipes"])).toBeUndefined();
  });

  it("treats a 401 from logout as success (an expired token cannot call it)", async () => {
    setToken("stale-token");
    server.use(
      http.post("/api/auth/logout", () =>
        HttpResponse.json({ detail: "not authenticated" }, { status: 401 }),
      ),
    );
    renderAuth();
    await waitFor(() => expect(status()).toBe("authenticated"));

    await userEvent.click(screen.getByRole("button", { name: "logout" }));

    await waitFor(() => expect(status()).toBe("anonymous"));
    expect(getToken()).toBeNull();
  });

  it("hydrates from a valid stored token on load", async () => {
    setToken("good-token");
    renderAuth();
    await waitFor(() => expect(status()).toBe("authenticated"));
    expect(screen.getByTestId("user")).toHaveTextContent("cook");
  });

  it("clears an expired stored token on load and lands anonymous", async () => {
    setToken("expired-token");
    server.use(
      http.get("/api/auth/me", () =>
        HttpResponse.json({ detail: "not authenticated" }, { status: 401 }),
      ),
    );
    renderAuth();
    await waitFor(() => expect(status()).toBe("anonymous"));
    expect(getToken()).toBeNull();
  });
});
