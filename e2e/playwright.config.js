// End-to-end checks for a branded FastHR careers instance.
// FASTHR_E2E_BASE_URLS: comma-separated origins (default https://hr.predictivelabs.ai).
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  timeout: 45000,
  retries: 0,
  reporter: [['list']],
  use: { headless: true, ignoreHTTPSErrors: false },
});
