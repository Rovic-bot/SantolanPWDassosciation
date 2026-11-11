/* Read-only public scrolling checks; dashboard uses saved synthetic aggregates. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/card-surface-scroll-2026-11-08';
const fixture = fs.readFileSync('.local/card-surface-scroll-20261108/dashboard.html', 'utf8');
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const errors = [], checks = [];
  try {
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    const readOnlyRoute = route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin || request.method() !== 'GET') return route.abort();
      if (url.pathname === '/dashboard/') return route.fulfill({ contentType: 'text/html', body: fixture });
      return route.continue();
    };
    await context.route('**/*', readOnlyRoute);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    const inspect = async viewport => {
      const state = await viewport.evaluate(el => ({
        overflow: getComputedStyle(el).overflowX,
        scrollbar: getComputedStyle(el).scrollbarWidth,
        webkitScrollbar: getComputedStyle(el, '::-webkit-scrollbar').display,
        width: el.clientWidth, scrollWidth: el.scrollWidth,
        cards: [...el.children].filter(card => card.matches('[data-swipe-card]')).map(card => ({
          hidden: card.hidden || card.inert || card.getAttribute('aria-hidden') === 'true',
          width: card.getBoundingClientRect().width, height: card.getBoundingClientRect().height,
          clipped: card.scrollHeight > card.clientHeight + 1
        }))
      }));
      assert.equal(state.overflow, 'auto');
      assert.equal(state.scrollbar, 'none');
      assert.equal(state.webkitScrollbar, 'none');
      assert(state.cards.length > 1);
      assert(state.cards.every(card => !card.hidden && !card.clipped && card.width <= state.width));
      await viewport.focus();
      await page.keyboard.press('End');
      assert(await viewport.evaluate(el => Math.abs(el.scrollLeft - (el.scrollWidth - el.clientWidth)) <= 1));
      await page.keyboard.press('Home');
      assert.equal(await viewport.evaluate(el => el.scrollLeft), 0);
      if (state.scrollWidth > state.width + 1) {
        await page.keyboard.press('ArrowRight');
        assert(await viewport.evaluate(el => el.scrollLeft > 0));
        await page.keyboard.press('Home');
        await viewport.hover();
        await page.mouse.wheel(0, 220);
        await page.waitForFunction(id => document.getElementById(id).scrollLeft > 0, await viewport.getAttribute('id'));
        await viewport.evaluate(el => { el.scrollLeft = 0; });
      }
      return state;
    };
    for (const width of [1920, 1440, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 960 });
      for (const [path, id] of [['/', 'home-guidance-cards'], ['/resources/', 'resource-guide-cards']]) {
        await page.goto(origin + path);
        await page.locator('[data-card-scroll].is-scrollable').waitFor();
        await page.evaluate(async () => { await document.fonts.ready; await new Promise(requestAnimationFrame); });
        const viewport = page.locator(`#${id}`);
        checks.push({ width, path, ...await inspect(viewport) });
        assert.equal(await page.locator('[data-card-scroll] [data-swipe-controls]').count(), 0);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        const last = viewport.locator('[data-swipe-card]').last();
        await last.evaluate(el => document.dispatchEvent(new CustomEvent('public:reveal', { detail: { target: el } })));
        assert(await last.evaluate(el => {
          const card = el.getBoundingClientRect(), boundary = el.parentElement.getBoundingClientRect();
          return card.left >= boundary.left - 1 && card.right <= boundary.right + 1;
        }));
        if (path === '/resources/') {
          const link = last.locator('a').first();
          if (await link.count()) {
            await viewport.evaluate(el => { el.scrollLeft = 0; });
            await link.focus();
            assert(await viewport.evaluate(el => el.scrollLeft > 0 || el.scrollWidth <= el.clientWidth));
          }
          await page.locator('.public-faq-summary').click();
          assert(await page.locator('#faq').evaluate(el => el.open));
          assert(await page.locator('#faq .is-ready').count());
        }
        if ([1440, 390].includes(width)) {
          await viewport.evaluate(el => { el.scrollLeft = 0; document.activeElement.blur(); });
          await viewport.locator('..').screenshot({ path: `${output}/${id}-${width}.png` });
        }
      }
      console.log(`Public cards passed at ${width}px`);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    for (const path of ['/', '/resources/']) {
      await page.goto(origin + path);
      await page.locator('[data-card-scroll].is-scrollable').waitFor();
      await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await inspect(page.locator('[data-card-scroll] [data-swipe-viewport]'));
      await page.emulateMedia({ media: 'print' });
      const printed = await page.locator('[data-card-scroll] [data-swipe-viewport]').evaluate(el => {
        const bounds = el.getBoundingClientRect();
        return [...el.children].every(card => card.getBoundingClientRect().left >= bounds.left - 1 && card.getBoundingClientRect().right <= bounds.right + 1);
      });
      assert(printed, 'Print includes every card in the document flow.');
      await page.emulateMedia({ media: 'screen' });
    }
    for (const theme of ['dark', 'light']) {
      for (const width of [1440, 390]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.goto(origin + '/dashboard/');
        await page.evaluate(theme => { document.documentElement.dataset.dashboardTheme = theme; }, theme);
        await page.locator('[data-chart="disability-bar"] svg').waitFor();
        const styles = await page.locator('.overview-section').evaluateAll(cards => cards.slice(0, 4).map(card => {
          const style = getComputedStyle(card);
          return { background: style.background, border: style.borderColor, shadow: style.boxShadow, backdrop: style.backdropFilter };
        }));
        assert.deepEqual(styles[0], styles[2]);
        assert.deepEqual(styles[1], styles[2]);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        checks.push({ theme, width, dashboard: styles });
        await page.locator('.overview-sections').screenshot({ path: `${output}/dashboard-${theme}-${width}.png` });
      }
    }
    const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    await phone.route('**/*', readOnlyRoute);
    phone.on('pageerror', error => errors.push(error.message));
    for (const [path, id] of [['/', 'home-guidance-cards'], ['/resources/', 'resource-guide-cards']]) {
      await phone.goto(origin + path);
      const viewport = phone.locator(`#${id}`);
      await phone.locator('[data-card-scroll].is-scrollable').waitFor();
      await viewport.scrollIntoViewIfNeeded();
      const point = await viewport.evaluate(el => { const r = el.getBoundingClientRect(); return { x: r.x + r.width * .8, y: Math.max(100, Math.min(700, r.y + 100)) }; });
      const cdp = await phone.context().newCDPSession(phone);
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [point] });
      for (let step = 1; step <= 7; step++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: point.x - step * 25, y: point.y }] });
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      await phone.waitForFunction(id => document.getElementById(id).scrollLeft > 30, id);
      await cdp.detach();
    }
    await phone.close();
    const plain = await browser.newPage({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
    await plain.route('**/*', readOnlyRoute);
    for (const path of ['/', '/resources/']) {
      await plain.goto(origin + path);
      const cards = plain.locator('[data-card-scroll] [data-swipe-card]');
      assert.equal(await cards.count(), await plain.locator('[data-card-scroll] [data-swipe-card]:visible').count());
      assert(await plain.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    }
    await plain.close();
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${output}/results.json`, JSON.stringify({ checks, errors, touch: true, largeText: true, keyboard: true, wheel: true, print: true, noJavaScript: true }, null, 2));
    console.log('Passed scrolling, accessibility, responsive layout and shared dashboard color checks.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
