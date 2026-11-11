const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, data = JSON.parse(process.env.QA_DATA), output = process.env.QA_OUTPUT;
  const errors = [], layouts = [], posts = [], reads = [];
  const cookie = {name: 'sessionid', value: process.env.QA_SESSION, url: base};
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, reducedMotion: 'reduce'});
    await context.addCookies([cookie]);
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== new URL(base).origin) return route.abort();
      if (request.method() === 'GET' && url.pathname === '/admin/ewaf') reads.push(url.href);
      if (request.method() !== 'GET') {
        assert.equal(request.method(), 'POST');
        assert.equal(url.pathname, data.workspace);
        posts.push(url.pathname);
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/admin/ewaf?selected=${data.ready}`);
    await page.locator(`[data-select-program="${data.ready}"][aria-pressed=true]`).waitFor();
    assert.equal(await page.locator('a[aria-current=page]').textContent(), 'EWAF');
    assert.match(await page.locator('.dashboard-location').textContent(), /Evidence-weighted ranking/);
    assert.equal(await page.locator('[data-selection-count]').textContent(), '5');
    assert.equal(await page.locator('[data-filter-submit]').isVisible(), false);
    assert.equal(await page.locator('.selection-hero, [data-selection-metrics], .selection-blockers').count(), 0);
    assert.doesNotMatch(await page.locator('[data-ewaf-selection]').textContent(), /Needs configuration|What needs attention|Rank with/);
    const panel = () => page.locator('[data-program-panel]:not([hidden])');
    await panel().locator('[data-generate-ranking] button').waitFor();
    assert.equal(await panel().locator('[data-generate-ranking] button').isEnabled(), true);
    assert.match(await panel().locator('.selection-gauge').getAttribute('aria-label'), /100 percent/);
    await page.evaluate(() => { window.ewafNavigationSentinel = 'same document'; });
    await page.locator(`[data-select-program="${data.other}"]`).focus();
    await page.keyboard.press('Space');
    assert.equal(await panel().getAttribute('data-program-panel'), data.other);
    await panel().locator('[data-generate-ranking] button').waitFor();
    assert.equal(await panel().locator('[data-generate-ranking] button').isDisabled(), true);
    assert.match(await panel().textContent(), /Pending scoring/);
    await page.locator(`[data-select-program="${data.ready}"]`).click();
    await page.locator('#ewaf-configuration').selectOption('review');
    await page.waitForFunction(() => document.querySelector('[data-selection-count]').textContent === '1');
    assert.equal(await page.locator('[data-program-row]:visible').count(), 1);
    await page.locator('#ewaf-program-search').fill('no program matches this');
    await page.getByRole('heading', {name: 'No EWAF programs found'}).waitFor();
    await page.locator('[data-selection-reset]').first().click();
    await page.waitForFunction(() => document.querySelector('[data-selection-count]').textContent === '5');
    await page.locator('#ewaf-program-search').fill(data.code);
    await page.waitForFunction(() => document.querySelector('[data-selection-count]').textContent === '1');
    assert.equal(await panel().getAttribute('data-program-panel'), data.ready);
    assert.equal(await page.evaluate(() => window.ewafNavigationSentinel), 'same document');
    assert.equal(posts.length, 0);
    assert.equal(reads.length, 1, 'Filtering and selection make no extra page requests');
    await page.locator('[data-selection-reset]').first().click();
    await page.waitForFunction(() => document.querySelector('[data-selection-count]').textContent === '5');
    await page.locator(`[data-select-program="${data.ready}"]`).click();
    for (const theme of ['dark', 'light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for (const width of [1600, 1440, 1280, 1024, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `${theme}/${width}: overflow`);
        assert.deepEqual(await page.evaluate(() => { const ids = [...document.querySelectorAll('[id]')].map(node => node.id); return ids.filter((id, i) => ids.indexOf(id) !== i); }), []);
        const queue = await page.locator('.selection-board').boundingBox();
        const rail = await page.locator('.selection-analysis').boundingBox();
        if (width >= 1200) {
          assert.ok(rail.x >= queue.x + queue.width, 'Analysis sits to the right of the queue');
          assert.equal(await page.locator('.selection-analysis').evaluate(node => getComputedStyle(node).position), 'sticky');
          assert.ok(rail.height <= 900, 'Rail remains within the viewport and can scroll');
        } else assert.ok(rail.y >= queue.y + queue.height, 'Analysis follows the queue on narrow screens');
        layouts.push({theme, width});
        if ([1600, 390].includes(width)) {
          await page.evaluate(() => scrollTo({top: 0, behavior: 'instant'}));
          await page.screenshot({path: path.join(output, `ewaf-selection-${theme}-${width}.png`), fullPage: true});
        }
      }
    }
    await page.evaluate(() => { document.documentElement.dataset.text = 'largest'; document.documentElement.dataset.contrast = 'true'; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.evaluate(() => { delete document.documentElement.dataset.text; delete document.documentElement.dataset.contrast; });
    await page.setViewportSize({width: 1600, height: 1000});
    await panel().locator('[data-generate-ranking] button').click();
    await panel().locator('[data-ranking-preview]').waitFor();
    assert.equal(new URL(page.url()).pathname, '/admin/ewaf');
    assert.equal(await panel().locator('.selection-preview li').count(), 3);
    assert.equal(posts.length, 1);
    assert.match(await panel().locator('.selection-preview header').textContent(), /Run 1/);
    await panel().getByRole('button', {name: 'Regenerate ranking'}).click();
    await page.waitForFunction(() => document.querySelector('[data-program-panel]:not([hidden]) .selection-preview header')?.textContent.includes('Run 2'));
    assert.equal(posts.length, 2);
    await page.screenshot({path: path.join(output, 'ewaf-generated-preview.png')});
    const nojs = await browser.newContext({javaScriptEnabled: false});
    await nojs.addCookies([cookie]);
    const fallback = await nojs.newPage();
    await fallback.goto(`${base}/admin/ewaf?selected=${data.other}`);
    assert.equal(await fallback.locator('[data-filter-submit]').isVisible(), true);
    assert.equal(await fallback.locator('[data-program-panel]:not([hidden])').getAttribute('data-program-panel'), data.other);
    await fallback.locator('#ewaf-program-search').fill(data.code);
    await fallback.locator('[data-filter-submit]').click();
    await fallback.waitForURL(url => url.searchParams.get('q') === data.code);
    assert.equal(await fallback.locator('[data-program-row]:visible').count(), 1);
    await nojs.close();
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({layouts, posts: posts.length, errors,
      checks: 'Instant selection; keyboard; automatic filters without reload; empty state; real readiness; disabled generation; two service-backed ranking saves; top-three saved ranks; responsive themes; scrollable rail; no-JS fallback'}, null, 2));
    console.log(`PASS: ${layouts.length} layouts, immediate filters and selection, two protected ranking generations.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
