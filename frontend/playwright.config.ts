import { defineConfig, devices } from '@playwright/test';

// Match the standard docker-compose frontend port. CI or a custom local server
// can still override this through E2E_BASE_URL.
const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:3003';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
