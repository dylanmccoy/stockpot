import { afterEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { client, request, setToken, setUnauthorizedHandler } from "./client";
import { ApiError, fieldName } from "../lib/apiError";
import type { ValidationIssue } from "../types";
import { rejection } from "../test/helpers";

afterEach(() => {
  setToken(null);
  setUnauthorizedHandler(null);
});

describe("api/client", () => {
  it("prefixes /api and returns the parsed JSON body", async () => {
    server.use(http.get("/api/ping", () => HttpResponse.json({ ok: true })));
    await expect(client.get("/ping")).resolves.toEqual({ ok: true });
  });

  it("serializes a JSON body and sets Content-Type only when there is one", async () => {
    let contentType: string | null = "unset";
    let raw = "";
    server.use(
      http.post("/api/echo", async ({ request: req }) => {
        contentType = req.headers.get("content-type");
        raw = await req.text();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    await client.post("/echo", { a: 1 });
    expect(contentType).toBe("application/json");
    expect(raw).toBe('{"a":1}');
  });

  it("injects Authorization: Bearer from localStorage", async () => {
    setToken("secret-token");
    let auth: string | null = null;
    server.use(
      http.get("/api/whoami", ({ request: req }) => {
        auth = req.headers.get("authorization");
        return HttpResponse.json({});
      }),
    );
    await client.get("/whoami");
    expect(auth).toBe("Bearer secret-token");
  });

  it("does not send Authorization on the public auth routes", async () => {
    setToken("secret-token");
    let auth: string | null = "unset";
    server.use(
      http.post("/api/auth/login", ({ request: req }) => {
        auth = req.headers.get("authorization");
        return HttpResponse.json({});
      }),
    );
    await client.post("/auth/login", { username: "a", password: "b" });
    expect(auth).toBeNull();
  });

  it("returns undefined for a 204 with no body", async () => {
    server.use(
      http.delete(
        "/api/things/1",
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    await expect(client.del("/things/1")).resolves.toBeUndefined();
  });

  it("normalizes a 422 ValidationIssue[] body, keeping the array intact", async () => {
    server.use(
      http.post("/api/things", () =>
        HttpResponse.json(
          {
            detail: [
              {
                loc: ["body", "username"],
                msg: "field required",
                type: "missing",
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    const err = await rejection(client.post("/things", {}));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(Array.isArray(err.detail)).toBe(true);
    const detail = err.detail as ValidationIssue[];
    expect(detail).toHaveLength(1);
    expect(fieldName(detail[0])).toBe("username");
  });

  it("normalizes a 422 string detail verbatim (not an array)", async () => {
    server.use(
      http.patch("/api/inventory/9", () =>
        HttpResponse.json(
          { detail: "quantity and unit must be set together" },
          { status: 422 },
        ),
      ),
    );
    const err = await rejection(client.patch("/inventory/9", {}));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.detail).toBe("quantity and unit must be set together");
  });

  it("falls back to a reason phrase when a non-2xx body has no usable detail", async () => {
    server.use(
      http.get("/api/boom", () =>
        HttpResponse.text("<html>502 Bad Gateway</html>", { status: 500 }),
      ),
    );
    const err = await rejection(client.get("/boom"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.detail).toBe("Internal Server Error");
  });

  it("fires the registered unauthorized handler on a 401 from a gated route", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    server.use(
      http.get("/api/recipes", () =>
        HttpResponse.json({ detail: "not authenticated" }, { status: 401 }),
      ),
    );
    await expect(client.get("/recipes")).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("does not fire the unauthorized handler on a 401 from login", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json(
          { detail: "invalid username or password" },
          { status: 401 },
        ),
      ),
    );
    const err = await rejection(
      client.post("/auth/login", { username: "a", password: "b" }),
    );
    expect(err.status).toBe(401);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("wraps a transport failure as an ApiError with status 0", async () => {
    server.use(http.get("/api/offline", () => HttpResponse.error()));
    const err = await rejection(request("/offline"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });
});
