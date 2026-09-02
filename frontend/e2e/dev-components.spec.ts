import { expect, test } from "@playwright/test";

/**
 * Visual pass of the primitive gallery. `/dev/components` is registered only
 * under `import.meta.env.DEV`, so this runs against the Vite dev server
 * (see `webServer` in playwright.config.ts), not a production build.
 */
test("dev component gallery renders", async ({ page }) => {
  await page.goto("/dev/components");

  await expect(
    page.getByRole("heading", { name: "Component demo", level: 1 }),
  ).toBeVisible();
  // Both forced-theme panes are always present in the DOM.
  await expect(page.getByRole("region", { name: "Light theme" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Dark theme" })).toBeVisible();

  // Let webfonts settle so text metrics are stable across runs.
  await page.evaluate(() => document.fonts.ready);

  await expect(page).toHaveScreenshot("dev-components.png", {
    fullPage: true,
    animations: "disabled",
  });
});
