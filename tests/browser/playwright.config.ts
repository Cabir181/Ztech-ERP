import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests run against the real application: a real Django process, a real
 * PostgreSQL database and the compiled interface served from the same origin.
 * Nothing here is stubbed - these tests exist to prove that what the interface
 * shows is what the server actually did.
 *
 * Start the stack first (see docs/testing.md), then:  npx playwright test
 */
export default defineConfig({
  testDir: ".",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "results.json" }]],
  use: {
    baseURL: process.env.ZTECH_BASE_URL ?? "http://127.0.0.1:8009",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1360, height: 900 },
        // The "Desktop Chrome" preset sets channel: "chromium", which makes
        // Playwright resolve its own bundled headless shell and ignore
        // executablePath. Clearing the channel is what lets a pre-provisioned
        // browser be used, which is how this runs in CI and in the container
        // image without downloading anything.
        channel: undefined,
        launchOptions: process.env.PLAYWRIGHT_CHROMIUM
          ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM }
          : {},
      },
    },
  ],
});
