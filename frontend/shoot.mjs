/**
 * Screenshot the dashboard for each ticket, for output/resolved_board.html.
 *
 *   node shoot.mjs
 *
 * Needs both servers up: uvicorn on 8000 and `npm run dev` on 5173.
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const SHOTS = resolve('../output/shots');
mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1600, height: 1150 },
  deviceScaleFactor: 2,
});

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
await page.waitForSelector('.ticket', { timeout: 20000 });

for (const id of [101, 102, 103]) {
  const card = page.locator('.ticket', { hasText: `#${id}` }).first();
  await card.click();
  // Wait for the panel heading to catch up and the replayed history to land.
  await page.waitForFunction(
    (t) => document.querySelector('.panel-head h2')?.textContent?.includes(`#${t}`),
    id,
    { timeout: 15000 },
  );
  await page.waitForTimeout(2500);

  const file = `${SHOTS}/ticket-${id}.png`;
  await page.screenshot({ path: file });
  const status = await page.locator('.panel-head .pill').first().textContent();
  const events = await page.locator('.feed .event').count();
  console.log(`ticket ${id}: "${status?.trim()}" · ${events} events · ${file}`);
}

// One wide shot of the whole board for the page header.
await page.locator('.ticket').first().click();
await page.waitForTimeout(1500);
await page.screenshot({ path: `${SHOTS}/board.png` });
console.log('board shot written');

await browser.close();
