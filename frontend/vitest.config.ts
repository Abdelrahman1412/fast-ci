import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
    // Honest defaults: no retries, and a focused test (.only) fails CI.
    retry: 0,
    allowOnly: !process.env.CI,
    passWithNoTests: false,
  },
});
