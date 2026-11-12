// Predictive Labs careers instance (hr.predictivelabs.*) smoke + apply flow.
//
//   cd e2e && npm i && npx playwright test
//   FASTHR_E2E_BASE_URLS=https://hr.predictivelabs.ai,https://hr.predictivelabs.ee
//   FASTHR_E2E_APPLY=1 FASTHR_E2E_ADMIN_EMAIL=... FASTHR_E2E_ADMIN_PASSWORD=...  (submit + delete a test application)
const { test, expect, request } = require('@playwright/test');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASES = (process.env.FASTHR_E2E_BASE_URLS || 'https://hr.predictivelabs.ai')
  .split(',').map((s) => s.trim().replace(/\/$/, '')).filter(Boolean);
const SITE = '/sites/predictivelabs';
const ET = { slug: 'riigihangete-spetsialist-el', title: 'Riigihangete spetsialist (EL)' };
const EN = { slug: 'public-procurement-specialist-eu', title: 'Public Procurement Specialist (EU)' };

for (const base of BASES) {
  test.describe(base, () => {
    test('home loads with Predictive Labs branding', async ({ page }) => {
      const res = await page.goto(base + '/');
      expect(res.status()).toBe(200);
      await expect(page.locator('.c-brand')).toContainText('Predictive Labs');
      await expect(page.locator('.c-brand img')).toHaveAttribute('src', /predictivelabs\.svg/);
      await expect(page.locator('footer')).toContainText('Predictive Labs OÜ');
      await expect(page.locator('a.c-powered')).toHaveText('Powered by FastHR');
      const brand = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue('--brand').trim().toLowerCase());
      expect(brand).toBe('#0d2a70');
      const logo = await page.request.get(base + '/static/brands/predictivelabs.svg');
      expect(logo.status()).toBe(200);
    });

    test('job list shows the job in Estonian and English', async ({ page }) => {
      await page.goto(base + SITE + '/et');
      await expect(page.locator('html')).toHaveAttribute('lang', 'et');
      await expect(page.locator('.job-card h3')).toContainText([ET.title]);
      await page.goto(base + SITE + '/en');
      await expect(page.locator('html')).toHaveAttribute('lang', 'en');
      await expect(page.locator('.job-card h3')).toContainText([EN.title]);
    });

    test('job detail opens from the list and the language switch works', async ({ page }) => {
      await page.goto(base + SITE + '/et');
      await page.locator('.job-card', { hasText: ET.title }).click();
      await expect(page).toHaveURL(new RegExp(`/et/jobs/${ET.slug}$`));
      await expect(page.locator('h1')).toHaveText(ET.title);
      await expect(page.locator('.copy')).toContainText('2000 € neto');
      await page.locator('.c-lang a', { hasText: 'EN' }).click();
      await expect(page).toHaveURL(new RegExp(`/en/jobs/${EN.slug}$`));
      await expect(page.locator('h1')).toHaveText(EN.title);
      await expect(page.locator('.copy')).toContainText('€2,000 net');
    });

    test('apply form renders (ET + EN)', async ({ page }) => {
      await page.goto(`${base}${SITE}/et/jobs/${ET.slug}`);
      const etForm = page.locator('form[action$="/apply"]');
      await expect(etForm.locator('button[type=submit]')).toHaveText('Saada avaldus');
      for (const name of ['first_name', 'last_name', 'email', 'cv', 'consent']) {
        await expect(etForm.locator(`[name=${name}]`)).toHaveCount(1);
      }
      await page.goto(`${base}${SITE}/en/jobs/${EN.slug}`);
      await expect(page.locator('form[action$="/apply"] button[type=submit]')).toHaveText('Submit application');
    });
  });
}

test('test application submits and is then deleted', async ({ page }) => {
  test.skip(process.env.FASTHR_E2E_APPLY !== '1' || !process.env.FASTHR_E2E_ADMIN_PASSWORD,
    'Set FASTHR_E2E_APPLY=1 and admin credentials to run the write test.');
  const base = BASES[0];
  const email = `e2e-${Date.now()}@example.com`;
  const cv = path.join(os.tmpdir(), `fasthr-e2e-cv-${Date.now()}.txt`);
  fs.writeFileSync(cv, 'Automated end-to-end test CV. Not a real candidate.\n');
  await page.goto(`${base}${SITE}/en/jobs/${EN.slug}`);
  const form = page.locator('form[action$="/apply"]');
  await form.locator('[name=first_name]').fill('E2E');
  await form.locator('[name=last_name]').fill('Test');
  await form.locator('[name=email]').fill(email);
  await form.locator('[name=cv]').setInputFiles(cv);
  await form.locator('[name=cover_note]').fill('Automated test application, please ignore.');
  await form.locator('[name=consent]').check();
  await form.locator('button[type=submit]').click();
  await expect(page.locator('h1')).toHaveText('Application received.');
  fs.unlinkSync(cv);

  const admin = await request.newContext({ baseURL: base });
  const login = await admin.post('/login', {
    form: { email: process.env.FASTHR_E2E_ADMIN_EMAIL, password: process.env.FASTHR_E2E_ADMIN_PASSWORD },
    maxRedirects: 0,
  });
  expect(login.status()).toBe(303);
  const del = await admin.post('/talent/privacy/delete-candidate', { form: { email } });
  expect(del.status()).toBe(200);
  expect((await del.json()).deleted).toBe(1);
  const again = await admin.post('/talent/privacy/delete-candidate', { form: { email } });
  expect(again.status()).toBe(404);
  await admin.dispose();
});
