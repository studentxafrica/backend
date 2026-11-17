// The admin portal's StudentXmas screen in Chromium against staging.
//
//   ADMIN_PASSWORD=... node admin-drops.mjs
import { chromium } from 'playwright';
import fs from 'node:fs';

const ADMIN = process.env.ADMIN_SITE || 'http://localhost:8080';
const RESULTS = process.env.RESULTS_DIR || '../../.state/results';
const results = [];
const record = (ok, check, detail = '') => {
  results.push({ status: ok ? 'PASS' : 'FAIL', check, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}     ${check}${detail ? ` — ${detail}` : ''}`);
};

const browser = await chromium.launch();
const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1360, height: 900 }, locale: 'en-KE' });
const page = await context.newPage();

try {
  await page.goto(ADMIN, { waitUntil: 'networkidle' });
  await page.fill('#email', 'staging-admin');
  await page.fill('#password', process.env.ADMIN_PASSWORD);
  await page.keyboard.press('Enter');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  await page.click('text=StudentXmas');
  await page.waitForSelector('text=Drops picked');
  record(true, 'StudentXmas screen opens from the sidebar');
  record(await page.getByText('Needs attention').isVisible(), 'Drops without a venue PIN are flagged');
  await page.screenshot({ path: `${RESULTS}/admin-drops.png`, fullPage: true });

  // Venue PIN for the ShopZetu voucher drop
  const shopzetu = page.locator('div.px-6', { hasText: 'ShopZetu voucher' }).first();
  await shopzetu.getByRole('button', { name: 'Venue PIN' }).click();
  await page.fill('#venue-pin', '4821');
  await page.click('text=Save PIN');
  await page.waitForSelector('text=Venue PIN saved');
  await shopzetu.getByText('Venue PIN set').waitFor();
  record(true, 'Venue PIN can be set, and the drop shows it');

  // Mark airtime sent for the first airtime recipient
  const airtime = page.locator('div.px-6', { hasText: /picked/ }).filter({ hasText: 'Safaricom airtime' }).first();
  await airtime.getByRole('button', { name: /picked/ }).click();
  const before = await page.getByRole('button', { name: 'Mark airtime sent' }).count();
  await page.getByRole('button', { name: 'Mark airtime sent' }).first().click();
  await page.waitForSelector('text=/Marked as sent to/');
  await page.waitForTimeout(800);
  const after = await page.getByRole('button', { name: 'Mark airtime sent' }).count();
  record(after === before - 1, 'Airtime can be marked as sent', `${before} → ${after} to send`);

  // Edit a drop's description
  await shopzetu.getByRole('button', { name: 'Edit' }).click();
  await page.fill('#drop-description', 'A ShopZetu voucher from StudentX for your holiday fit. Show your StudentX pass at checkout within 10 days.');
  await page.click('role=button[name="Save"]');
  await page.waitForSelector('text=Drop updated');
  record(true, 'A drop can be edited');
  await page.screenshot({ path: `${RESULTS}/admin-drops-after.png`, fullPage: true });
} catch (e) {
  record(false, 'Admin run completed', String(e).slice(0, 300));
  await page.screenshot({ path: `${RESULTS}/admin-drops-failure.png`, fullPage: true }).catch(() => {});
} finally {
  fs.writeFileSync(`${RESULTS}/admin-browser.json`, JSON.stringify(results, null, 2));
  await browser.close();
}
