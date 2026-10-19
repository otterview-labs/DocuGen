import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  outputDir: '../artifacts/playwright',
  workers: 1,
  use: { baseURL: process.env.QUILL_TEST_URL || 'http://127.0.0.1:18080' },
});
