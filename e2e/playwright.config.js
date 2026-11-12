// End-to-end checks for a branded FastHR careers instance.
// FASTHR_E2E_BASE_URLS  comma-separated origins (default https://hr.predictivelabs.ai)
// FASTHR_E2E_RESOLVE    optional "host1,host2=IP" to test before DNS propagates
// FASTHR_E2E_INSECURE=1 accept not-yet-issued TLS certificates (pre-DNS only)
const { defineConfig } = require('@playwright/test');

const args = [];
if (process.env.FASTHR_E2E_RESOLVE) {
  const [hosts, ip] = process.env.FASTHR_E2E_RESOLVE.split('=');
  args.push('--host-resolver-rules=' + hosts.split(',').map((h) => `MAP ${h.trim()} ${ip.trim()}`).join(','));
}

module.exports = defineConfig({
  testDir: '.',
  timeout: 45000,
  retries: 0,
  workers: 2,
  reporter: [['list']],
  use: {
    headless: true,
    ignoreHTTPSErrors: process.env.FASTHR_E2E_INSECURE === '1',
    launchOptions: { args },
  },
});
