import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { cleanup } from "@testing-library/react";
import { server } from "./test/server";

// Start the MSW server once for the whole suite. `onUnhandledRequest: "error"`
// makes any un-mocked request a hard failure, so no test can hit the network.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

afterEach(() => {
  server.resetHandlers();
  cleanup();
  try {
    localStorage.clear();
  } catch {
    /* storage unavailable in this environment */
  }
});

afterAll(() => server.close());
