import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

const jsonResponse = (body: unknown, init: ResponseInit = { status: 200 }) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("list() GETs /api/recipes and returns the parsed body", async () => {
    const rows = [{ id: 1, title: "Pancakes", ingredients: "", instructions: "", created_at: "" }];
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(rows));

    await expect(api.list()).resolves.toEqual(rows);
    expect(fetch).toHaveBeenCalledWith("/api/recipes");
  });

  it("create() POSTs JSON", async () => {
    const input = { title: "Soup", ingredients: "", instructions: "" };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ id: 2, ...input, created_at: "" }, { status: 201 }));

    await api.create(input);

    expect(fetch).toHaveBeenCalledWith("/api/recipes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  });

  it("remove() tolerates a 204 with no body", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(api.remove(3)).resolves.toBeUndefined();
  });

  it("throws on a non-2xx response", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response("nope", { status: 500, statusText: "Internal Server Error" }));
    await expect(api.list()).rejects.toThrow("500");
  });
});
