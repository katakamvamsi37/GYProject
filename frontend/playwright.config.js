import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5179',
    browserName: 'chromium',
    channel: 'msedge',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: '..\\.venv\\Scripts\\python.exe ..\\scripts\\test_server.py',
      url: 'http://127.0.0.1:8011/api/',
      timeout: 60000,
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5179 --strictPort',
      url: 'http://127.0.0.1:5179',
      timeout: 60000,
      reuseExistingServer: false,
      env: { API_PROXY_TARGET: 'http://127.0.0.1:8011' },
    },
  ],
});
