import { act, renderHook, waitFor } from "@testing-library/react";
import { onlineManager } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";
import { useIsOffline } from "./connectivity";

// `onlineManager` is a module-level singleton shared with the rest of the
// suite — always leave it back online so other tests' queries never come up
// paused.
afterEach(() => {
  onlineManager.setOnline(true);
});

describe("useIsOffline", () => {
  it("reflects onlineManager's current state, live", async () => {
    const { result } = renderHook(() => useIsOffline());
    expect(result.current).toBe(false);

    act(() => onlineManager.setOnline(false));
    await waitFor(() => expect(result.current).toBe(true));

    act(() => onlineManager.setOnline(true));
    await waitFor(() => expect(result.current).toBe(false));
  });
});
