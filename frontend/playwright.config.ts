import { defineConfig } from "@playwright/test";

// End-to-end tests of the main flows against `next dev` and the stub (docs/frontend.md §11).
// `npm run test:e2e` uses a server that's already running, or starts one.

export default defineConfig({
  testDir: "./e2e",
  // Named *.e2e.ts, so Vitest, which runs *.test.ts and *.spec.ts, leaves them alone.
  testMatch: "*.e2e.ts",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  // One at a time: each test plays real video, and they all use the stub's one test student.
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    // Without a real click, Chrome may refuse to start video with sound. The refusal is the
    // player's normal path, but these tests are about what happens after it.
    launchOptions: { args: ["--autoplay-policy=no-user-gesture-required"] },
  },
  // Playwright's own Chromium can't play H.264, our video format, so use the installed browsers.
  projects: [
    { name: "chrome", use: { channel: "chrome" } },
    { name: "edge", use: { channel: "msedge" } },
  ],
  webServer: {
    command: "npm run dev",
    cwd: "..",
    url: "http://localhost:3000/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
