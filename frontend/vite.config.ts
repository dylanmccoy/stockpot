import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend so the frontend can use same-origin fetches.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
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
