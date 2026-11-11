/* Read-only responsive announcement QA; larger datasets exist only in browser responses. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict'), fs = require('node:fs');
const origin = process.env.QA_URL || 'http://127.0.0.1:8013';
const output = process.env.QA_OUTPUT || 'docs/public-announcement-four-card-swipe-2026-11-09';
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  try {
    fs.mkdirSync(output, { recursive: true });
    const errors = [], checks = [];
    const page = await browser.newPage({ reducedMotion: 'reduce' });
    page.on('pageerror', error => errors.push(error.message));
    const deck = page.locator('.notice-swipe-carousel');
    const visible = deck.locator('[data-swipe-card]:not([hidden])');
    const status = deck.locator('[data-swipe-status]');
    async function change(target, action) {
      const before = await target.locator('.notice-swipe-carousel [data-swipe-status]').textContent();
      await action();
      await target.waitForFunction(before => document.querySelector('.notice-swipe-carousel [data-swipe-status]')?.textContent !== before, before);
    }
    async function inspect(target) {
      return target.locator('.notice-swipe-carousel').evaluate(el => {
        const viewport = el.querySelector('[data-swipe-viewport]'), boundary = viewport.getBoundingClientRect();
        const cards = [...el.querySelectorAll('[data-swipe-card]:not([hidden])')];
        return {
          columns: Math.max(1, Math.min(el.querySelectorAll('[data-swipe-card]').length, Number(el.dataset.swipeMaxColumns), Math.floor((boundary.width + 18) / (Number(el.dataset.swipeMinWidth) + 18)))),
          rows: new Set(cards.map(card => Math.round(card.getBoundingClientRect().top))).size,
          width: boundary.width, height: boundary.height,
          cards: cards.map(card => {
            const r = card.getBoundingClientRect();
            return { id: card.dataset.qaNotice, width: r.width, overflow: card.scrollHeight - card.clientHeight,
              fits: r.left >= boundary.left - 1 && r.right <= boundary.right + 1 && r.top >= boundary.top - 1 && r.bottom <= boundary.bottom + 1, inert: card.inert };
          }),
          hiddenInert: [...el.querySelectorAll('[hidden][data-swipe-card]')].every(card => card.inert && card.getAttribute('aria-hidden') === 'true'),
          pageFits: document.documentElement.scrollWidth <= innerWidth + 1,
          fillsWidth: Math.abs(boundary.width - document.querySelector('.notice-main').getBoundingClientRect().width) < 2,
          resultsCalloutRemoved: !document.querySelector('.notice-results-callout'),
          dotCount: el.querySelectorAll('[data-swipe-page]').length,
          activeDots: el.querySelectorAll('[data-swipe-page][aria-current="true"]').length
        };
      });
    }
    function validate(layout) {
      assert.equal(layout.rows, 1);
      assert(layout.cards.length <= layout.columns);
      assert(layout.hiddenInert && layout.pageFits && layout.fillsWidth && layout.resultsCalloutRemoved);
      assert(layout.dotCount <= 7 && layout.activeDots === 1);
      assert(layout.cards.every(card => card.fits && !card.inert && card.overflow <= 1));
    }
    // Capture actual published content, without adding demo records.
    for (const width of [1920, 1440, 390]) {
      await page.setViewportSize({ width, height: 960 });
      assert.equal((await page.goto(origin + '/announcements/')).status(), 200);
      await page.waitForSelector('.notice-swipe-carousel.is-ready');
      validate(await inspect(page));
      await deck.screenshot({ path: `${output}/cards-${width}.png` });
      await page.screenshot({ path: `${output}/announcements-${width}.png`, fullPage: true });
      if (width === 390 && await deck.locator('[data-swipe-page="1"]').count()) {
        await change(page, () => deck.locator('[data-swipe-page="1"]').click());
        assert.equal(await deck.locator('[aria-current="true"]').getAttribute('data-swipe-page'), '1');
        await deck.screenshot({ path: `${output}/mobile-second-card.png` });
      }
    }
    async function fixtures(target) {
      await target.route('**/announcements/**', async route => {
        const url = new URL(route.request().url());
        if (url.pathname !== '/announcements/' || url.searchParams.has('q') || url.searchParams.has('category')) return route.continue();
        const response = await route.fetch();
        let html = await response.text();
        const source = html.match(/<article class="notice-row"[\s\S]*?<\/article>/g);
        assert(source?.length);
        const number = Number(url.searchParams.get('page')) === 2 ? 2 : 1;
        const count = number === 1 ? 24 : 7, start = number === 1 ? 1 : 25;
        const cards = Array.from({ length: count }, (_, index) => source[index % source.length]
          .replace('data-swipe-card', `data-swipe-card data-qa-notice="${start + index}"`)
          .replace(/(<h3><a[^>]*>)/, `$1Sample ${start + index}: `)).join('');
        let first = true;
        html = html.replace(/<article class="notice-row"[\s\S]*?<\/article>/g, () => {
          if (!first) return ''; first = false; return cards;
        }).replace(/data-swipe-start="\d+"/, `data-swipe-start="${start}"`).replace(/data-swipe-total="\d+"/, 'data-swipe-total="31"');
        const links = number === 1 ? '<a href="?page=2" rel="next">Next</a>' : '<a href="?page=1" rel="prev">Previous</a>';
        html = html.replace('<div class="notice-list-footer">', `<div class="notice-list-footer"><nav id="announcement-pagination" class="notice-pagination" aria-label="Announcement pages">${links}</nav>`);
        await route.fulfill({ response, body: html });
      });
    }
    await fixtures(page);
    for (const width of [1920, 1440, 992, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 960 });
      await page.goto(origin + '/announcements/');
      await page.waitForSelector('.notice-swipe-carousel.is-ready');
      const initial = await inspect(page), seen = new Set();
      assert.equal(initial.cards.length, initial.columns);
      if (width >= 1440) assert.equal(initial.columns, 4);
      await change(page, () => deck.locator('[data-swipe-page="1"]').click());
      assert.equal(await page.evaluate(() => document.activeElement.id), 'announcement-cards');
      assert.equal(await deck.locator('[aria-current="true"]').getAttribute('data-swipe-page'), '1');
      await change(page, () => deck.locator('[data-swipe-page="0"]').click());
      for (let attempt = 0; attempt < 32; attempt++) {
        const layout = await inspect(page);
        validate(layout);
        layout.cards.forEach(card => seen.add(card.id));
        if (await deck.locator('[data-swipe-next]').getAttribute('aria-disabled') === 'true') break;
        await change(page, () => deck.locator('[data-swipe-next]').click());
      }
      assert.equal(seen.size, 31, 'Every notice must be reachable across server batches.');
      checks.push({ width, columns: initial.columns, visible: initial.cards.length, rows: initial.rows, noticesReached: seen.size });
    }
    // Crossing back into a prior server batch must reveal its last group.
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.goto(origin + '/announcements/?page=2');
    await deck.locator('[data-swipe-viewport]').focus();
    await change(page, () => page.keyboard.press('ArrowLeft'));
    const pageSize = (await inspect(page)).columns;
    assert.equal(await status.textContent(), `Cards ${25 - pageSize} to 24 of 31`);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'announcement-cards');
    await change(page, () => page.keyboard.press('ArrowRight'));
    assert.equal(await status.textContent(), `Cards 25 to ${Math.min(24 + pageSize, 31)} of 31`);
    assert.equal(await page.evaluate(() => document.querySelector('#announcement-cards').getAnimations({ subtree: true }).length), 0);
    // Normal-motion dragging must change groups without opening a link.
    await page.goto(origin + '/announcements/');
    await page.waitForSelector('.notice-swipe-carousel.is-ready');
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await visible.first().scrollIntoViewIfNeeded();
    const box = await visible.first().boundingBox();
    await change(page, async () => {
      await page.mouse.move(box.x + box.width * .8, box.y + 110);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width * .2, box.y + 110, { steps: 8 });
      await page.mouse.up();
    });
    assert.equal(await status.textContent(), `Cards ${pageSize + 1} to ${pageSize * 2} of 31`);
    assert.equal(await page.locator('dialog[open]').count(), 0);
    const trigger = visible.first().locator('.notice-row-action');
    await trigger.click();
    await page.waitForSelector('[data-public-dialog][open] [data-public-popup-content]');
    await page.keyboard.press('Escape');
    assert(await trigger.evaluate(el => el === document.activeElement));
    // Resize keeps the focused card available; long copy and large text remain readable.
    await page.setViewportSize({ width: 320, height: 960 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    await page.waitForFunction(() => [...document.querySelectorAll('.notice-row:not([hidden])')].every(el => el.scrollHeight <= el.clientHeight + 1));
    validate(await inspect(page));
    await page.emulateMedia({ media: 'print' });
    assert.equal(await deck.locator('[data-swipe-card]:visible').count(), await deck.locator('[data-swipe-card]').count());
    await page.emulateMedia({ media: 'screen', reducedMotion: 'reduce' });
    await page.evaluate(() => document.documentElement.style.removeProperty('font-size'));
    await page.setViewportSize({ width: 1440, height: 960 });
    // Filters and history replace the deck in place and keep its controls operational.
    await page.evaluate(() => { window.announcementQAMarker = 'same-document'; });
    async function update(action) {
      await action();
      await page.waitForFunction(() => document.querySelector('.public-browse-status')?.textContent === 'Results updated.' && !document.querySelector('[data-public-browser][aria-busy]'));
      assert.equal(await page.evaluate(() => window.announcementQAMarker), 'same-document');
    }
    await update(() => page.locator('.notice-topic-links a').filter({ hasText: 'Program Results' }).click());
    validate(await inspect(page));
    await update(() => page.locator('.notice-topic-links a').filter({ hasText: /^All$/ }).click());
    await change(page, () => deck.locator('[data-swipe-next]').click());
    await page.locator('#announcement-search').fill('no-such-public-announcement-qa');
    await update(() => page.locator('.notice-search button').click());
    assert.equal(await page.locator('.notice-empty:visible').count(), 1);
    await update(() => page.goBack());
    await page.waitForSelector('.notice-swipe-carousel.is-ready');
    await change(page, () => deck.locator('[data-swipe-next]').click());
    const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    phone.on('pageerror', error => errors.push(error.message));
    await fixtures(phone);
    await phone.goto(origin + '/announcements/');
    const touch = await phone.context().newCDPSession(phone);
    for (const direction of [-1, 1]) {
      const card = phone.locator('.notice-row:not([hidden])').first();
      await card.scrollIntoViewIfNeeded();
      const point = await card.evaluate((el, direction) => { const r = el.getBoundingClientRect(); return { x: r.x + r.width * (direction < 0 ? .8 : .2), y: r.y + 100 }; }, direction);
      await change(phone, async () => {
        await touch.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [point] });
        for (let i = 1; i <= 6; i++) await touch.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: point.x + direction * i * 20, y: point.y }] });
        await touch.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      });
    }
    assert.equal(await phone.locator('dialog[open]').count(), 0);
    await phone.close();
    const plain = await browser.newPage({ javaScriptEnabled: false });
    await plain.goto(origin + '/announcements/');
    assert.equal(await plain.locator('[data-swipe-card]:visible').count(), await plain.locator('[data-swipe-card]').count());
    await plain.close();
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${output}/results.json`, JSON.stringify({ checks, errors, responsiveSingleRow: true, dotNavigation: true, simulated31Notices: true, batchNavigationBothDirections: true, touchBothDirections: true, mouseSwipe: true, keyboard: true, popup: true, filters: true, history: true, largeText: true, print: true, noJavaScript: true }, null, 2));
    console.log('Responsive announcements passed: one row, responsive columns, dots, all 31 notices reachable, swipe, keyboard, filters and fallbacks.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
