import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const PORT = 4173;

/**
 * End-to-end tests against the real thing: the built UI served by `narcisse serve --demo`, on a
 * fresh data directory, with the fake module running three times faster than in the demo.
 */
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: 'fr-FR',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'desktop', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run build && cd .. && uv run narcisse serve --demo --no-browser --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/info`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      NARCISSE_DATA_DIR: mkdtempSync(join(tmpdir(), 'narcisse-e2e-')),
      NARCISSE_SPEED: '3',
    },
  },
});
