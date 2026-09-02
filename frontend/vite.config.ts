import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend so the frontend can use
// same-origin fetches. `VITE_API_PROXY_TARGET` overrides the target so the
// `integration` Playwright config can point a throwaway dev server at its own
// isolated backend instead of the default :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    css: false,
    // Playwright owns `e2e/` — keep its specs out of the Vitest run.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
