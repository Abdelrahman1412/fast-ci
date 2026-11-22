import { defineConfig, devices } from '@playwright/test';

const CI = !!process.env.CI;
const lane = process.env.E2E_LANE ?? 'mock';
const env = (name: string, fallback: number) => (process.env[name] ? Number(process.env[name]) : fallback);

export default defineConfig({
  fullyParallel: true,
  // A stray test.only must not turn a 30-test suite into a 1-test green run.
  forbidOnly: CI,
  retries: env('PW_RETRIES', 0),
  // A test that passes only on retry is flaky; with this on, it fails the run.
  failOnFlakyTests: process.env.PW_FAIL_ON_FLAKY === '1',
  workers: process.env.PW_WORKERS ? Number(process.env.PW_WORKERS) : undefined,
  // Sharded CI runs write blob reports that one job merges into a single HTML report.
  reporter: CI ? [['blob'], ['github'], ['list']] : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  projects: [
    { name: 'mock', testDir: 'e2e/mock' },
    { name: 'full', testDir: 'e2e/full' },
  ],
  webServer: [
    // Serves the already-built dist/ folder. CI builds once and hands dist/ to every shard.
    { command: 'pnpm preview', url: 'http://127.0.0.1:4173', reuseExistingServer: !CI, timeout: 30_000 },
    ...(lane === 'full'
      ? [{ command: 'node server/demo-api.mjs', url: 'http://127.0.0.1:4010/api/health', reuseExistingServer: !CI }]
      : []),
  ],
});
