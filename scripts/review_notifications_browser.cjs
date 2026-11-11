/* Synthetic, offline browser checks: real templates/assets; mocked aggregate responses. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = path.resolve(process.env.REVIEW_QA_ROOT || '.');
const output = path.join(root, '.local/dashboard-badges-20261111');
const base = 'http://review.test';
const fixtures = new Map([
  ['/membership/reviews/', path.join(output, 'membership.html')],
  ['/admin/programs/', path.join(output, 'programs.html')],
  ['/admin/programs', path.join(output, 'programs.html')],
  ['/dashboard/', path.join(root, '.local/dashboard-charts-20261029/after.html')],
]);
const mime = {'.css': 'text/css', '.js': 'application/javascript', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2'};

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
  const errors = [];
  let count = 4, denied = false, broken = false, countRequests = 0;
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    assert.equal(request.method(), 'GET');
    assert.equal(url.origin, base);
    if (url.pathname === '/workspace/review-counts/') {
      countRequests++;
      if (denied) return route.fulfill({status: 403, body: 'Denied'});
      if (broken) return route.fulfill({status: 503, body: 'Unavailable'});
      const cards = Object.fromEntries((url.searchParams.get('programs') || '').split(',').filter(Boolean).map(id => [id, count]));
      return route.fulfill({json: {membership: count * 2, association: count, pdao: count, programs: count, program_cards: cards}});
    }
    if (url.pathname.includes('new-count')) return route.fulfill({json: {new_count: 0}});
    if (fixtures.has(url.pathname)) return route.fulfill({contentType: 'text/html; charset=utf-8', body: fs.readFileSync(fixtures.get(url.pathname))});
    if (url.pathname.startsWith('/static/')) {
      const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
      assert(file.startsWith(path.join(root, 'static') + path.sep));
      if (fs.existsSync(file)) return route.fulfill({contentType: mime[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file)});
    }
    return route.fulfill({status: 404, body: 'Outside fixture'});
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  async function refreshCounts() {
    const previous = countRequests;
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForFunction(() => true);
    for (let i = 0; i < 30 && previous === countRequests; i++) await page.waitForTimeout(50);
    assert(countRequests > previous);
  }
  try {
    await page.goto(base + '/membership/reviews/');
    const association = page.locator('[data-review-count="association"]');
    await page.waitForFunction(() => document.querySelector('[data-review-count="association"]').textContent === '4');
    for (const theme of ['light', 'dark']) {
      await page.evaluate(value => document.documentElement.dataset.dashboardTheme = value, theme);
      for (const width of [1440, 390]) {
        await page.setViewportSize({width, height: 1000});
        assert(await association.isVisible());
        assert(await page.locator('[data-review-count="pdao"]').isVisible());
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.screenshot({path: path.join(output, `membership-${theme}-${width}.png`), fullPage: true});
      }
    }
    count = 0; await refreshCounts(); await association.waitFor({state: 'hidden'});
    count = 7; await refreshCounts(); await association.waitFor({state: 'visible'});
    await page.waitForFunction(() => document.querySelector('[data-review-count="association"]').textContent === '7');
    broken = true; await refreshCounts(); assert.equal(await association.textContent(), '7'); broken = false;

    // The application replaces the whole workspace body when switching tabs.
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('[data-group-key="programs"] summary').click();
    await page.getByRole('link', {name: /Program Management/}).click();
    await page.waitForURL(/\/admin\/programs\/?$/);
    await page.waitForFunction(() => document.querySelector('[data-review-count="program"]')?.textContent === '7');
    const program = page.locator('[data-review-count="program"]');
    assert(await program.isVisible());
    for (const theme of ['light', 'dark']) {
      await page.evaluate(value => document.documentElement.dataset.dashboardTheme = value, theme);
      for (const width of [1440, 390]) {
        await page.setViewportSize({width, height: 1000});
        assert(await program.isVisible());
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.screenshot({path: path.join(output, `programs-${theme}-${width}.png`), fullPage: true});
      }
    }
    // Filter replacements must also receive subsequent polling updates.
    await page.evaluate(() => {
      const card = document.querySelector('[data-review-count="program"]');
      const replacement = card.cloneNode(true);
      replacement.dataset.programCountId = '11111111-1111-4111-8111-111111111111';
      card.replaceWith(replacement);
    });
    count = 9; await refreshCounts();
    await page.waitForFunction(() => document.querySelector('[data-review-count="program"]').textContent === '9');
    denied = true; await refreshCounts(); await program.waitFor({state: 'hidden'}); denied = false;

    await page.goto(base + '/dashboard/');
    await page.waitForSelector('[data-chart="age-histogram"] svg');
    assert.equal(await page.getByText('More metrics & reporting details').count(), 0);
    assert.equal(await page.locator('[data-chart-id="age-histogram"]').getByText('Could not load').count(), 0);
    await page.locator('[data-chart-id="age-histogram"]').screenshot({path: path.join(output, 'age-chart.png')});
    assert.deepEqual(errors, []);
    console.log('Passed: chart rendering, removed metrics, dark/light desktop/mobile badges, zero/new/error/revoked counts, workspace navigation and replaced program cards.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
