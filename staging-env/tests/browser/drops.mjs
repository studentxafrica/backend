// Festive Drops journey in Chromium against staging, after a staging-only
// simulation has picked some drops (see the staging run notes on SFD-14).
//
//   PICKED_VOUCHER=kevin NOT_PICKED=brian CREW=otieno node drops.mjs
import { chromium } from 'playwright';
import fs from 'node:fs';

const SITE = process.env.SITE || 'http://localhost:8081';
const RESULTS = process.env.RESULTS_DIR || '../../.state/results';
const PASSWORD = process.env.PASSWORD || 'Drops-test-1';
const who = (name) => `${process.env[name]}.drops@staging.invalid`;
const results = [];
const record = (ok, check, detail = '') => {
  results.push({ status: ok ? 'PASS' : 'FAIL', check, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}     ${check}${detail ? ` — ${detail}` : ''}`);
};

const browser = await chromium.launch();
const newPage = async () => {
  // A real browser locale: the container's default (en-US@posix) breaks Intl number formatting.
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 412, height: 915 }, isMobile: true, locale: 'en-KE', timezoneId: 'Africa/Nairobi' });
  const page = await context.newPage();
  page.on('response', (r) => {
    if (r.url().includes('/api/v1/') && r.status() >= 400) console.log(`API ${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  });
  return page;
};
const shot = (page, name, fullPage = false) => page.screenshot({ path: `${RESULTS}/drops-${name}.png`, fullPage });

async function signIn(page, email) {
  await page.goto(`${SITE}/auth?page=login`, { waitUntil: 'networkidle' });
  await page.fill('input[type="email"]', email);
  await page.click('button[type="submit"]');
  await page.waitForSelector('input[type="password"]');
  await page.fill('input[type="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith('/auth'), { timeout: 15000 });
  // Let the site finish storing the signed-in user before the next full page load.
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
}

try {
  // Visitor: next drop first, ended drops in their own list
  let page = await newPage();
  await page.goto(`${SITE}/drops`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#upcoming-heading');
  const upcomingTitles = await page.locator('section[aria-labelledby="upcoming-heading"] h3').allTextContents();
  const firstLabel = await page.locator('section[aria-labelledby="upcoming-heading"] a').first().textContent();
  const endedCount = await page.locator('section[aria-labelledby="ended-heading"] a').count();
  const endedLabels = await page.locator('section[aria-labelledby="ended-heading"] a span.absolute').allTextContents();
  record(firstLabel.includes('NEXT DROP'), 'Next available drop is listed first and marked', upcomingTitles[0]);
  record(endedCount === 4 && endedLabels.every((l) => l === 'ENDED'), 'Ended drops are in their own list, marked ENDED', `${endedCount} ended`);
  record(await page.getByText('Join StudentXmas').first().isVisible(), 'Visitor is invited to join StudentXmas');
  const homePage = await newPage();
  await homePage.goto(SITE, { waitUntil: 'networkidle' });
  const banner = homePage.getByRole('link', { name: /Now on · StudentXmas/ });
  record(await banner.isVisible() && (await banner.getAttribute('href')) === '/drops', 'Home page announces StudentXmas and links to /drops');
  await banner.scrollIntoViewIfNeeded();
  await shot(homePage, 'home-banner');
  await shot(page, 'visitor-top');
  await page.locator('#ended-heading').scrollIntoViewIfNeeded();
  await shot(page, 'visitor-ended');

  // Member who wasn't picked: celebrate message
  page = await newPage();
  await signIn(page, who('NOT_PICKED'));
  await page.goto(`${SITE}/drops`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Not this time');
  const celebrate = page.getByRole('link', { name: /Celebrate them on @studentxafrica/ });
  record(await celebrate.isVisible(), 'Not-picked member is invited to celebrate on @studentxafrica',
    await celebrate.getAttribute('href'));
  record(await page.getByText(/still in every remaining drop/).isVisible(), 'Not-picked member is told about upcoming drops');
  await shot(page, 'not-picked');
  const notPickedPage = page;

  // Member picked for a voucher: result, profile, live pass, venue check
  page = await newPage();
  await signIn(page, who('PICKED_VOUCHER'));
  await page.goto(`${SITE}/drops`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=/You have a perk from StudentXmas/');
  record(true, 'A member picked earlier sees their perk on the drops page');
  await shot(page, 'perk-waiting');
  await page.click('section[aria-labelledby="ended-heading"] a:has-text("PICKED FOR YOU")');
  await page.waitForSelector('text=You were picked!');
  record(true, 'The drop they were picked for says "You were picked!"');
  await shot(page, 'picked');
  await page.goto(`${SITE}/me?tab=drops`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Show my StudentX pass');
  record(true, 'Profile Drops tab lists the perk with its next step');
  await shot(page, 'profile-tab');
  await page.click('text=Show my StudentX pass');
  await page.waitForSelector('text=Show at the counter');
  const code = (await page.locator('.font-mono').textContent()).replace(' ', '');
  record(/^[A-Z0-9]{6}$/.test(code), 'Live pass shows a server code', code);
  await shot(page, 'pass');

  const venue = await newPage();
  await venue.goto(`${SITE}/pass-check`, { waitUntil: 'networkidle' });
  await venue.fill('#pass-code', code);
  await venue.click('button[type="submit"]');
  await venue.waitForSelector('text=Valid pass');
  record(true, 'Venue check accepts the live code');
  await shot(venue, 'venue-check');

  // Crew: picked member shares the link, a friend joins
  page = await newPage();
  await signIn(page, who('CREW'));
  await page.goto(`${SITE}/me?tab=drops`, { waitUntil: 'networkidle' });
  await page.click('text=/Add your crew/');
  await page.waitForSelector('text=Waiting for a friend');
  const link = await page.locator('main .truncate').textContent();
  await shot(page, 'crew-before');
  await notPickedPage.goto(`http://${link}`.replace('http://localhost:8081', SITE), { waitUntil: 'networkidle' });
  await notPickedPage.click('text=Join the crew');
  await notPickedPage.waitForSelector("text=You're in the crew.");
  record(true, 'A friend joins the crew from the invite link');
  await shot(notPickedPage, 'crew-joined');
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('text=/[1-3] of 3 verified/');
  record(true, 'Crew page shows the friend as verified');
  await shot(page, 'crew-after');
  // A new student: short sign-up from the campaign, join straight away, see the series
  page = await newPage();
  const email = `new-${Date.now()}@staging.invalid`;
  await page.goto(`${SITE}/drops`, { waitUntil: 'networkidle' });
  await page.click('a:has-text("Join StudentXmas")');
  await page.waitForSelector('input[type="email"]');
  await page.fill('input[type="email"]', email);
  await page.click('button[type="submit"]');
  await page.waitForSelector('input[type="password"]');
  await page.fill('input[type="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector('#first-name');
  await page.fill('#first-name', 'Neema');
  await page.fill('#last-name', 'Test');
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => u.pathname === '/drops', { timeout: 15000 });
  record(true, 'Sign-up from the campaign asks only for a name and returns to it');
  await page.waitForSelector('#drops-phone');
  await page.fill('#drops-phone', '0711 222 333');
  await page.check('text=/I agree to the/');
  await page.click('button:has-text("Join StudentXmas")');
  await page.waitForSelector("text=You're in. One step left");
  record(await page.getByText('Your StudentXmas').first().isVisible(), 'New student joins at once and is asked to verify before the next pick');
  await shot(page, 'new-member-series');

} catch (e) {
  record(false, 'Browser run completed', String(e).slice(0, 300));
  for (const ctx of browser.contexts()) {
    for (const [i, p] of ctx.pages().entries()) await p.screenshot({ path: `${RESULTS}/drops-failure-${browser.contexts().indexOf(ctx)}-${i}.png`, fullPage: true }).catch(() => {});
  }
} finally {
  fs.writeFileSync(`${RESULTS}/drops-browser.json`, JSON.stringify(results, null, 2));
  await browser.close();
}
