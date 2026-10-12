import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const PORT = 4174;

/**
 * The graph's benchmark (`npm run bench`): fictitious graphs of growing size, in a real browser,
 * against `narcisse serve --demo` on a fresh data directory. Headless Chrome draws WebGL in
 * software unless told to use the GPU: these flags ask for it (the table says which renderer drew).
 */
const GPU = [
  '--ignore-gpu-blocklist',
  '--enable-gpu',
  ...(process.platform === 'win32' ? ['--use-angle=d3d11'] : []),
];
export default defineConfig({
  testDir: 'bench',
  testMatch: '*.bench.ts',
  workers: 1,
  timeout: 300_000,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: 'fr-FR',
    viewport: { width: 1600, height: 1000 },
    launchOptions: { args: GPU },
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1600, height: 1000 } },
    },
  ],
  webServer: {
    command: `npm run build && cd .. && uv run narcisse serve --demo --no-browser --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/info`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: { NARCISSE_DATA_DIR: mkdtempSync(join(tmpdir(), 'narcisse-bench-')) },
  },
});
