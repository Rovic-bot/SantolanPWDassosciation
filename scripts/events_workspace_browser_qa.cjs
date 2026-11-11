const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, url = base + process.env.QA_ROUTE, output = process.env.QA_OUTPUT;
  const cookie = {name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: base};
  const errors = [], writes = [], checks = [];
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, colorScheme: 'dark', reducedMotion: 'reduce'});
    await context.addCookies([cookie]);
    await context.route(base + '/**', route => {
      if (route.request().method() !== 'GET') { writes.push(route.request().method()); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    let documents = 0;
    page.on('request', request => { if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents++; });
    await page.goto(url + '?month=' + process.env.QA_MONTH);
    assert.equal(await page.locator('.event-agenda-card').count(), 7);
    assert.equal(await page.locator('.event-quarter').count(), 4);
    assert.equal(await page.locator('a.event-observance-row').count(), 12);
    assert.equal(await page.locator('[data-event-submit]').isVisible(), false);
    assert.equal(await page.locator('a[aria-current=page]').textContent(), 'Events Calendar');
    assert.equal(await page.getByRole('link', {name: 'Create event', exact: false}).getAttribute('href'), '/events/manage/new/');
    assert.equal(await page.locator('.event-metrics, .event-capacity, [data-event-readiness]').count(), 0);
    const assertCompactAgenda = async () => {
      const visible = await page.locator('.event-agenda-list').evaluate(list => {
        list.scrollTop = 0;
        const bounds = list.getBoundingClientRect();
        const cards = [...list.querySelectorAll('.event-agenda-card')];
        return {count: cards.filter(card => {
          const box = card.getBoundingClientRect();
          return box.top < bounds.bottom - 2 && box.bottom > bounds.top + 2;
        }).length, scrollable: list.scrollHeight > list.clientHeight + 20};
      });
      assert.equal(visible.count, 3, 'Exactly three events visible in the list');
      assert.equal(visible.scrollable, true, 'Remaining events scroll within the agenda');
    };
    await page.waitForFunction(() => document.querySelector('.event-agenda-list').style.getPropertyValue('--agenda-visible-height'));
    await assertCompactAgenda();
    const observanceTop = await page.locator('.event-observances').evaluate(node => node.getBoundingClientRect().top);
    await page.locator('.event-agenda-list').evaluate(node => { node.scrollTop = node.scrollHeight; });
    assert.equal(await page.locator('.event-observances').evaluate(node => node.getBoundingClientRect().top), observanceTop);
    assert.equal(await page.locator('.event-agenda-list').evaluate(node => node.scrollTop > 0), true);
    await page.locator('.event-agenda-list').evaluate(node => { node.scrollTop = 0; });
    const search = page.locator('#event-search'), type = page.locator('#event-category'), status = page.locator('#event-status');
    const settled = async (values, count) => page.waitForFunction(({values, count}) => {
      const params = new URL(location.href).searchParams;
      const results = document.querySelector('[data-event-results]');
      return Object.entries(values).every(([key, value]) => (params.get(key) || '') === value) &&
        results?.getAttribute('aria-busy') !== 'true' && Number(results?.dataset.resultCount) === count;
    }, {values, count});
    const before = documents;
    await search.fill('Medical'); await settled({q: 'Medical'}, 1);
    assert.equal(await search.evaluate(node => node === document.activeElement), true);
    await search.fill('covered court'); await settled({q: 'covered court'}, 1);
    assert.match(await page.locator('.event-agenda-card h2').textContent(), /Assistive Device/);
    await search.fill('no matching activity'); await settled({q: 'no matching activity'}, 0);
    assert.equal(await page.getByRole('heading', {name: 'No events found'}).isVisible(), true);
    await page.locator('.event-empty [data-event-reset]').click(); await settled({q: ''}, 7);
    await type.selectOption('specific'); await settled({category: 'specific'}, 2);
    await page.locator('.event-filter-footer summary').click();
    await status.selectOption('draft'); await settled({category: 'specific', status: 'draft'}, 0);
    await type.selectOption('general'); await settled({category: 'general', status: 'draft'}, 1);
    await page.locator('form [data-event-reset]').click(); await settled({q: ''}, 7);
    await page.locator('#event-period').selectOption('past'); await settled({period: 'past'}, 1);
    assert.match(await page.locator('.event-agenda-card h2').textContent(), /Past community gathering/);
    await page.locator('#event-period').selectOption('all'); await settled({period: 'all'}, 8);
    await page.locator('form [data-event-reset]').click(); await settled({q: ''}, 7);

    // Calendar browsing and day selection work without replacing the document.
    const initialMonth = await page.locator('[name=month]').inputValue();
    await page.getByRole('link', {name: 'Next month', exact: true}).click();
    await page.waitForFunction(month => document.querySelector('[data-event-results]').dataset.month !== month &&
      document.querySelector('[data-event-results]').getAttribute('aria-busy') !== 'true', initialMonth);
    await page.goBack();
    await page.waitForFunction(month => document.querySelector('[data-event-results]').dataset.month === month &&
      document.querySelector('[data-event-results]').getAttribute('aria-busy') !== 'true', initialMonth);
    const dayLink = page.locator(`.event-calendar-day[href*="day=${process.env.QA_DAY}"]`);
    await dayLink.focus(); await page.keyboard.press('Enter');
    await settled({day: process.env.QA_DAY, period: 'all'}, 1);
    assert.equal(await page.locator('.event-agenda').evaluate(node => node === document.activeElement), true);
    await page.locator('.event-date-filter a').click();
    await settled({day: ''}, 8);
    await page.locator('form [data-event-reset]').click(); await settled({q: ''}, 7);

    await search.fill('Medical'); await settled({q: 'Medical'}, 1);
    await page.locator('form [data-event-reset]').click(); await settled({q: ''}, 7);
    await page.route('**/admin/events?**', async route => {
      if (new URL(route.request().url()).searchParams.get('q') === 'Medical') await new Promise(resolve => setTimeout(resolve, 700));
      return route.continue();
    });
    const request = page.waitForRequest(request => new URL(request.url()).searchParams.get('q') === 'Medical');
    await search.fill('Medical'); await request;
    await search.fill('PWD Sports'); await settled({q: 'PWD Sports'}, 1);
    await page.waitForTimeout(750);
    assert.match(await page.locator('.event-agenda-card h2').textContent(), /PWD Sports/);
    await page.unroute('**/admin/events?**');
    await search.fill('Pending search');
    await page.locator('form [data-event-reset]').click(); await settled({q: ''}, 7);
    await page.waitForTimeout(400);
    assert.equal(new URL(page.url()).searchParams.get('q'), null);
    await search.dispatchEvent('compositionstart'); await search.fill('Medical');
    await page.waitForTimeout(400); assert.equal(new URL(page.url()).searchParams.get('q'), null);
    await search.dispatchEvent('compositionend'); await settled({q: 'Medical'}, 1);
    await page.locator('form [data-event-reset]').click(); await settled({q: ''}, 7);
    await page.route('**/admin/events?**', route => route.fulfill({status: 503, body: 'Unavailable'}));
    await search.fill('Medical'); await page.getByText('Could not update events.', {exact: false}).waitFor();
    assert.equal(await page.locator('.event-agenda-card').count(), 7);
    await page.unroute('**/admin/events?**');
    await search.press('Enter'); await settled({q: 'Medical'}, 1);
    await page.locator('form [data-event-reset]').click(); await settled({q: ''}, 7);
    assert.equal(documents, before, 'Filters or calendar reloaded the document');
    await status.selectOption('published'); await settled({status: 'published'}, 5);
    await page.locator('.event-filter-footer summary').click();

    for (const theme of ['dark', 'light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for (const width of [1600, 1440, 1280, 1024, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        await page.evaluate(async () => {
          scrollTo({top: 0, behavior: 'instant'}); await document.fonts.ready;
          await Promise.all(document.getAnimations().filter(animation => Number.isFinite(animation.effect.getComputedTiming().endTime)).map(animation => animation.finished.catch(() => {})));
          await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame);
        });
        const layout = await page.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
          return {overflow: document.documentElement.scrollWidth > innerWidth + 1,
            duplicates: ids.filter((id, index) => ids.indexOf(id) !== index)};
        });
        assert.equal(layout.overflow, false, `${theme} ${width}px page overflow`);
        assert.deepEqual(layout.duplicates, []);
        await assertCompactAgenda();
        checks.push({theme, width});
        if ([1600, 390].includes(width)) {
          await page.evaluate(async () => {
            for (let top = 0; top < document.documentElement.scrollHeight; top += innerHeight) {
              scrollTo({top, behavior: 'instant'}); await new Promise(requestAnimationFrame);
            }
            scrollTo({top: 0, behavior: 'instant'}); await new Promise(requestAnimationFrame);
          });
          await page.screenshot({path: path.join(output, `events-${theme}-${width}.png`), fullPage: true});
        }
      }
      await page.setViewportSize({width: 1600, height: 1000});
      const agenda = await page.locator('.event-agenda').boundingBox();
      const operations = await page.locator('.event-operations').boundingBox();
      assert.ok(operations.x >= agenda.x + agenda.width, 'Calendar remains to the right');
      assert.equal(await page.locator('.event-operations').evaluate(node => getComputedStyle(node).position), 'sticky');
      await page.screenshot({path: path.join(output, `events-sticky-${theme}.png`)});
      await page.reload();
      assert.equal(await page.locator('html').getAttribute('data-dashboard-theme'), theme);
      // Reload opens the advanced section because the status filter is active.
      if (await page.locator('.event-filter-footer details').getAttribute('open') !== null) await page.locator('.event-filter-footer summary').click();
    }
    await page.setViewportSize({width: 390, height: 1000});
    await page.evaluate(() => { document.documentElement.dataset.text = 'largest'; document.documentElement.dataset.contrast = 'true'; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.emulateMedia({forcedColors: 'active'});
    assert.equal(await page.locator('.event-calendar-day.has-events').first().isVisible(), true);
    const observance = page.locator('a.event-observance-row').first();
    const editUrl = await observance.getAttribute('href');
    await observance.focus(); await page.keyboard.press('Enter');
    await page.waitForURL(base + editUrl);
    assert.equal(await page.getByRole('button', {name: 'Save and publish', exact: true}).isVisible(), true);

    const fallback = await browser.newContext({javaScriptEnabled: false});
    await fallback.addCookies([cookie]);
    const plain = await fallback.newPage();
    await plain.goto(url);
    await plain.locator('#event-search').fill('Medical');
    await Promise.all([plain.waitForNavigation(), plain.getByRole('button', {name: 'Apply filters'}).click()]);
    assert.equal(await plain.locator('.event-agenda-card').count(), 1);
    await fallback.close();
    assert.deepEqual(errors, []); assert.deepEqual(writes, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({checks, errors, writes,
      interactions: 'Three visible events, independent agenda scrolling, live search/location/type/status/date filters, calendar month/back and day keyboard selection, no document reloads, stale requests, IME, reset, error recovery, observance editor and no-JavaScript fallback',
      layout: '14 responsive combinations, sticky operations, theme persistence, large text/high contrast/forced colors/reduced motion, no overflow or duplicate IDs'}, null, 2));
    console.log(`PASS: ${checks.length} responsive checks; compact agenda, month/day navigation, observance links and no-JavaScript fallback.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
