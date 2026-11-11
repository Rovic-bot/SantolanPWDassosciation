const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], writes = [], checks = [];
  const base = process.env.QA_URL, url = base + process.env.QA_PORTFOLIO_ROUTE;
  const cookie = {name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: base};
  const output = process.env.QA_OUTPUT;
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, reducedMotion: 'reduce', colorScheme: 'dark'});
    await context.addCookies([cookie]);
    await context.route(base + '/**', route => {
      if (route.request().method() !== 'GET') { writes.push(route.request().method()); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    let documents = 0;
    page.on('request', request => { if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents++; });
    await page.goto(url);
    assert.equal(await page.locator('[data-portfolio-submit]').isVisible(), false);
    assert.equal(await page.locator('[data-portfolio-count]').textContent(), '8');
    assert.equal(await page.locator('.portfolio-program').count(), 8);
    assert.match(await page.locator('.portfolio-featured h2').textContent(), /Medical Access Week/);
    assert.match(await page.locator('.portfolio-deadline').textContent(), /Medical Access Week/);
    assert.equal(await page.locator('a[aria-current=page]').textContent(), 'Program Management');
    await page.screenshot({path: path.join(output, 'portfolio-initial-desktop.png'), fullPage: true});
    const settled = async (query, category, status, count) => page.waitForFunction(({query, category, status, count}) => {
      const params = new URL(location.href).searchParams;
      const results = document.querySelector('[data-portfolio-results]');
      return (params.get('q') || '') === query && (params.get('assistance_type') || '') === category &&
        (params.get('status') || '') === status && results?.getAttribute('aria-busy') !== 'true' &&
        Number(results?.dataset.resultCount) === count;
    }, {query, category, status, count});
    const search = page.locator('#program-search'), category = page.locator('#program-type'), status = page.locator('#program-status');
    const before = documents;
    await search.fill('Medical');
    await settled('Medical', '', '', 1);
    assert.equal(await search.evaluate(node => node === document.activeElement), true);
    await search.fill(process.env.QA_FIRST_CODE);
    await settled(process.env.QA_FIRST_CODE, '', '', 1);
    await search.fill('Unknown program');
    await settled('Unknown program', '', '', 0);
    assert.equal(await page.getByRole('heading', {name: 'No programs found'}).isVisible(), true);
    await page.locator('.portfolio-empty [data-portfolio-reset]').click();
    await settled('', '', '', 8);
    await category.selectOption('Community');
    await settled('', 'Community', '', 2);
    await status.selectOption('draft');
    await settled('', 'Community', 'draft', 1);
    assert.match(await page.locator('.portfolio-program h2').textContent(), /Family Caregiver Forum/);
    await page.locator('form [data-portfolio-reset]').click();
    await settled('', '', '', 8);
    await status.selectOption('closed');
    await settled('', '', 'closed', 1);
    assert.equal(await page.locator('.portfolio-program .portfolio-status').textContent(), 'Published');
    assert.match(await page.locator('.portfolio-excess').textContent(), /1 application above capacity/);
    await page.locator('form [data-portfolio-reset]').click();
    await settled('', '', '', 8);
    await page.locator('.portfolio-more-filters summary').click();
    await page.locator('[name=with_applications]').check();
    await settled('', '', '', 6);
    await page.locator('[name=registration]').selectOption('open');
    await settled('', '', '', 5);
    await page.locator('[name=sort]').selectOption('az');
    await page.waitForFunction(() => new URL(location.href).searchParams.get('sort') === 'az');
    assert.match(await page.locator('.portfolio-featured h2').textContent(), /Assistive Device Distribution/);
    await page.locator('form [data-portfolio-reset]').click();
    await settled('', '', '', 8);
    await page.locator('.portfolio-more-filters summary').click();

    // A slow earlier request cannot replace newer results or a clear action.
    await page.route('**/admin/programs?**', async route => {
      if (new URL(route.request().url()).searchParams.get('q') === 'Medical') await new Promise(resolve => setTimeout(resolve, 700));
      return route.continue();
    });
    const requested = page.waitForRequest(request => new URL(request.url()).searchParams.get('q') === 'Medical');
    await search.fill('Medical');
    await requested;
    await search.fill('Digital');
    await settled('Digital', '', '', 1);
    await page.waitForTimeout(750);
    assert.match(await page.locator('.portfolio-program h2').textContent(), /Digital Skills Workshop/);
    await search.fill('Pending search');
    await page.locator('form [data-portfolio-reset]').click();
    await settled('', '', '', 8);
    await page.waitForTimeout(400);
    assert.equal(new URL(page.url()).searchParams.get('q'), '');
    await page.unroute('**/admin/programs?**');
    await search.dispatchEvent('compositionstart');
    await search.fill('Medical');
    await page.waitForTimeout(400);
    assert.equal(new URL(page.url()).searchParams.get('q'), '');
    await search.dispatchEvent('compositionend');
    await settled('Medical', '', '', 1);
    await page.locator('form [data-portfolio-reset]').click();
    await settled('', '', '', 8);
    assert.equal(documents, before, 'Filters caused a document navigation');

    // Failure is recoverable without discarding the visible list.
    await page.route('**/admin/programs?**', route => route.fulfill({status: 503, body: 'Unavailable'}));
    await search.fill('Medical');
    await page.getByText('Could not update programs.', {exact: false}).waitFor();
    assert.equal(await page.locator('.portfolio-program').count(), 8);
    await page.unroute('**/admin/programs?**');
    await search.press('Enter');
    await settled('Medical', '', '', 1);
    assert.equal(await page.locator('[data-portfolio-submit]').isVisible(), false);
    await page.locator('form [data-portfolio-reset]').click();
    await settled('', '', '', 8);

    for (const theme of ['dark', 'light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for (const width of [1600, 1440, 1280, 1024, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        await page.evaluate(async () => {
          scrollTo({top: 0, behavior: 'instant'});
          await document.fonts.ready;
          await Promise.all(document.getAnimations().filter(animation => Number.isFinite(animation.effect.getComputedTiming().endTime)).map(animation => animation.finished.catch(() => {})));
          await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame);
        });
        const layout = await page.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
          const cards = [...document.querySelectorAll('.portfolio-program')].map(node => node.getBoundingClientRect().toJSON());
          return {overflow: document.documentElement.scrollWidth > innerWidth + 1, cards,
            duplicates: ids.filter((id, index) => ids.indexOf(id) !== index)};
        });
        assert.equal(layout.overflow, false, `${theme} ${width}px page overflow`);
        assert.deepEqual(layout.duplicates, []);
        if (width >= 768) {
          assert.ok(layout.cards[0].width > layout.cards[1].width * 1.9, 'Featured card must span both columns');
          assert.ok(Math.abs(layout.cards[1].y - layout.cards[2].y) < 1, 'Paired cards must align');
          assert.ok(Math.abs(layout.cards[1].height - layout.cards[2].height) < 1, 'Paired cards must have equal height');
        }
        checks.push({theme, width});
        if ([1600, 390].includes(width)) {
          // Warm offscreen glass layers before Chrome captures a long page after resizing.
          await page.evaluate(async () => {
            for (let top = 0; top < document.documentElement.scrollHeight; top += innerHeight) {
              scrollTo({top, behavior: 'instant'}); await new Promise(requestAnimationFrame);
            }
            scrollTo({top: 0, behavior: 'instant'}); await new Promise(requestAnimationFrame);
          });
          await page.screenshot({path: path.join(output, `portfolio-${theme}-${width}.png`), fullPage: true});
          if (width === 390) {
            await page.locator('.portfolio-filters').scrollIntoViewIfNeeded();
            await page.screenshot({path: path.join(output, `portfolio-mobile-filters-${theme}.png`)});
            await page.locator('.portfolio-featured').scrollIntoViewIfNeeded();
            assert.equal(await page.getByRole('link', {name: 'Medical Access Week', exact: true}).isVisible(), true);
            await page.screenshot({path: path.join(output, `portfolio-mobile-card-${theme}.png`)});
          }
        }
      }
      await page.setViewportSize({width: 1600, height: 1000});
      const top = await page.locator('[data-portfolio-results]').evaluate(node => node.getBoundingClientRect().top + scrollY + 200);
      await page.evaluate(top => scrollTo({top, behavior: 'instant'}), top);
      await page.evaluate(() => new Promise(requestAnimationFrame));
      const first = await page.locator('.portfolio-operations').boundingBox();
      await page.evaluate(() => scrollBy({top: 200, behavior: 'instant'}));
      await page.evaluate(() => new Promise(requestAnimationFrame));
      const second = await page.locator('.portfolio-operations').boundingBox();
      assert.ok(Math.abs(first.y - second.y) < 1, `${theme}: Operations panel must stay sticky`);
      assert.ok(second.y >= 76 && second.y + second.height <= 1000);
      await page.screenshot({path: path.join(output, `portfolio-sticky-${theme}.png`)});
      await page.reload();
      assert.equal(await page.locator('html').getAttribute('data-dashboard-theme'), theme, 'Theme persistence');
    }
    await page.setViewportSize({width: 390, height: 1000});
    await page.evaluate(() => { document.documentElement.dataset.text = 'largest'; document.documentElement.dataset.contrast = 'true'; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await search.focus();
    assert.equal(await search.evaluate(node => getComputedStyle(node).outlineStyle !== 'none' || getComputedStyle(node).boxShadow !== 'none'), true);
    await page.emulateMedia({forcedColors: 'active'});
    assert.equal(await page.locator('.portfolio-gauge').isVisible(), true);

    const fallback = await browser.newContext({javaScriptEnabled: false});
    await fallback.addCookies([cookie]);
    const plain = await fallback.newPage();
    await plain.goto(url);
    await plain.locator('#program-status').selectOption('draft');
    await Promise.all([plain.waitForNavigation(), plain.getByRole('button', {name: 'Apply filters'}).click()]);
    assert.equal(await plain.locator('.portfolio-program').count(), 2);
    await fallback.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({checks, errors, writes,
      workflow: 'Live search and code lookup, combined category/status filters, registration and sort, excess capacity, reset, stale-response protection, IME, error recovery; no document reloads',
      accessibility: 'Focus preserved, large text, high contrast, forced colors, reduced motion and no-JavaScript form',
      layout: 'Featured card, aligned pairs, sticky operations, persisted themes'}, null, 2));
    console.log(`PASS: ${checks.length} responsive checks, immediate filters without navigation, recovery, sticky operations and no-JavaScript fallback.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
