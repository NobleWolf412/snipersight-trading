import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for the visual snapshot framework only.
 *
 * Viewport is intentionally NOT set here — each SnapshotState declares its
 * own viewport (default 1440×900 from states.ts) and capture.spec.ts calls
 * page.setViewportSize() explicitly. The 0×0 headless render bug from
 * Phase 2 was real; setViewportSize on every test bypasses it.
 */
export default defineConfig({
  testDir: './tests/visual',
  testMatch: /capture\.spec\.ts$/,
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 4,
  reporter: [
    ['list'],
    ['json', { outputFile: 'tests/visual/__report__/playwright.json' }],
  ],
  outputDir: 'tests/visual/__report__/playwright-output',
  use: {
    baseURL: process.env.SNAPSHOT_BASE_URL || 'http://localhost:5000',
    trace: 'retain-on-failure',
    screenshot: 'off',  // We take our own screenshots in capture.spec.ts.
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
});
