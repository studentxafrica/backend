// Drives the real student site (served by staging) through sign-up and the
// ID upload step in Chromium, and records what the site sends to the API.
//
//   cd staging-env/tests/browser && npm install && npx playwright install chromium
//   node signup.mjs
import { chromium } from 'playwright';
import fs from 'node:fs';

const SITE = process.env.SITE || 'http://localhost:8081';
const RESULTS = process.env.RESULTS_DIR || '../../.state/results';
const results = [];
const record = (status, check, detail = '') => {
  results.push({ status, check, detail });
  console.log(`${status.padEnd(8)} ${check}${detail ? ` — ${detail}` : ''}`);
};

const browser = await chromium.launch();
const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 412, height: 915 }, isMobile: true });
const page = await context.newPage();
const apiCalls = [];
page.on('response', async (res) => {
  if (res.url().includes('/api/v1/')) {
    let body = res.request().postData() || '';
    apiCalls.push({ method: res.request().method(), url: res.url(), status: res.status(), body: body.slice(0, 2000) });
  }
});
const dialogs = [];
page.on('dialog', async (d) => { dialogs.push(d.message()); await d.dismiss(); });

try {
  // Home page, as a visitor from "link in bio" sees it
  await page.goto(SITE, { waitUntil: 'networkidle' });
  const missing = apiCalls.filter((c) => c.status === 404);
  record(missing.length ? 'FINDING' : 'PASS', 'Home page API calls all succeed (F-26)',
    missing.map((c) => `${c.status} ${new URL(c.url).pathname}`).join(', '));
  const offerCalls = apiCalls.filter((c) => /offer\/(latest|featured|highlighted)/.test(c.url));
  record(offerCalls.length ? 'PASS' : 'FAIL', 'Home page loads offers from the API', `${offerCalls.length} offer requests`);

  // Sign-up
  const email = `browser-${Date.now()}@staging.invalid`;
  await page.goto(`${SITE}/auth?page=signup`, { waitUntil: 'networkidle' });
  await page.fill('input[type="email"]', email);
  await page.click('button[type="submit"]');
  await page.waitForSelector('input[type="password"]', { timeout: 15000 });
  await page.fill('input[type="password"]', 'Browser-pass-1');
  await page.click('button[type="submit"]');

  await page.waitForSelector('input[placeholder="Jane"]', { timeout: 15000 });
  await page.fill('input[placeholder="Jane"]', 'Akinyi');
  await page.fill('input[placeholder="Doe"]', 'Browser');
  await page.fill('input[placeholder="Enter phone number"]', '+254712345678');
  const uni = page.locator('input[placeholder="Start typing your university..."]');
  await uni.fill('University of Nairobi');
  await page.keyboard.press('Escape');
  await page.fill('input[type="date"]', '2004-05-17');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);

  const register = apiCalls.find((c) => c.url.includes('/auth/user/consumer/register'));
  if (!register) {
    record('FAIL', 'Site sends the registration', `calls: ${apiCalls.map((c) => new URL(c.url).pathname).join(', ')}`);
  } else {
    record(register.status === 201 ? 'PASS' : 'FAIL', 'Site sends the registration', `HTTP ${register.status}`);
    const sent = JSON.parse(register.body || '{}');
    record('phone' in sent ? 'PASS' : 'FINDING', 'Registration includes the phone number the form asked for (F-20)',
      `fields sent: ${Object.keys(sent).join(', ')}`);
  }

  // ID upload step: a typical phone photo of 6 MB, then a 3 MB one
  const fileInput = page.locator('input[type="file"]');
  if (await fileInput.count()) {
    const big = Buffer.alloc(6 * 1024 * 1024, 0);
    await fileInput.setInputFiles({ name: 'id-photo.jpg', mimeType: 'image/jpeg', buffer: big });
    await page.waitForTimeout(1000);
    const refused = dialogs.find((m) => /5MB/i.test(m));
    record(refused ? 'FINDING' : 'PASS', 'A 6 MB phone photo is accepted at the ID step (F-25)', refused ? `browser alert: "${refused}"` : '');
  } else {
    record('FAIL', 'Reached the ID upload step', 'no file input found');
  }

  const anyPhone = apiCalls.some((c) => c.body.includes('712345678'));
  record(anyPhone ? 'PASS' : 'FINDING', 'Phone number reaches the API at any point in sign-up (F-20)',
    anyPhone ? '' : 'not sent in any request');
  await page.screenshot({ path: `${RESULTS}/signup-last-step.png`, fullPage: true });
} catch (e) {
  record('FAIL', 'Browser run completed', String(e).slice(0, 300));
  await page.screenshot({ path: `${RESULTS}/signup-error.png`, fullPage: true }).catch(() => {});
} finally {
  fs.mkdirSync(RESULTS, { recursive: true });
  fs.writeFileSync(`${RESULTS}/browser.json`, JSON.stringify({ results, apiCalls }, null, 2));
  await browser.close();
}
