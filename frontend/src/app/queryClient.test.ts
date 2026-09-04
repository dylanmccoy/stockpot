import { describe, expect, it } from "vitest";
import { ApiError } from "../lib/apiError";
import { createQueryClient } from "./queryClient";

// `createQueryClient` builds the production defaults (spec §11 O-5). The
// predicate is deliberate, not the old blanket `retry: 1`: only a transport
// failure (`ApiError.status === 0`, api/client.ts) is worth retrying — a real
// API error is a settled answer from the server.
describe("createQueryClient defaults", () => {
  const { queries, mutations } = createQueryClient().getDefaultOptions();

  it("retries a network failure up to 5 attempts, then gives up", () => {
    const retry = queries!.retry as (
      count: number,
      err: unknown,
    ) => boolean;
    const networkErr = new ApiError(0, "Network request failed");
    expect(retry(0, networkErr)).toBe(true);
    expect(retry(4, networkErr)).toBe(true);
    expect(retry(5, networkErr)).toBe(false);
  });

  it.each([404, 409, 422, 500])(
    "never retries a real %i API error",
    (status) => {
      const retry = queries!.retry as (
        count: number,
        err: unknown,
      ) => boolean;
      expect(retry(0, new ApiError(status, "conflict"))).toBe(false);
    },
  );

  it("never retries a non-ApiError throw", () => {
    const retry = queries!.retry as (
      count: number,
      err: unknown,
    ) => boolean;
    expect(retry(0, new Error("boom"))).toBe(false);
  });

  it("backs off exponentially, capped at 30s", () => {
    const retryDelay = queries!.retryDelay as (count: number) => number;
    expect(retryDelay(0)).toBe(1000);
    expect(retryDelay(1)).toBe(2000);
    expect(retryDelay(4)).toBe(16_000);
    expect(retryDelay(10)).toBe(30_000);
  });

  it("treats every query as immediately stale (nothing here polls, so 0 costs no extra requests)", () => {
    expect(queries!.staleTime).toBe(0);
  });

  it("refetches on reconnect but not on window focus", () => {
    expect(queries!.refetchOnReconnect).toBe(true);
    expect(queries!.refetchOnWindowFocus).toBe(false);
  });

  it("never auto-retries a mutation", () => {
    expect(mutations!.retry).toBe(false);
  });
});
