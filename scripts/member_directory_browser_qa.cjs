const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], checks = [];
  const url = process.env.QA_URL + process.env.QA_DIRECTORY_ROUTE;
  const output = process.env.QA_OUTPUT;
  const cookie = {name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL};
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, reducedMotion: 'reduce', colorScheme: 'dark'});
    await context.addCookies([cookie]);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await page.locator('[data-select-member][role=button]').first().waitFor();
    assert.equal(await page.locator('[data-directory-count]').textContent(), '21');
    assert.equal(await page.locator('[data-select-member]').count(), 20);
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Ana Reyes');
    assert.match(await page.locator('[data-preview-note]').textContent(), /Synthetic note/);
    assert.equal(await page.locator('.directory-register').getAttribute('href'), '/admin/members/registration');
    const originalUrl = page.url();
    const second = page.locator(`[data-select-member="${process.env.QA_SECOND_ID}"]`);
    await second.focus();
    await page.keyboard.press('Space');
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Ben Santos');
    assert.equal(await second.getAttribute('aria-pressed'), 'true');
    assert.equal(page.url(), originalUrl);
    assert.match(await page.locator('[data-preview-full]').getAttribute('href'), new RegExp(`/members/${process.env.QA_SECOND_ID}/$`));
    assert.match(await page.locator('[data-preview-edit]').getAttribute('href'), /\/edit\/$/);
    await page.locator(`[data-select-member="${process.env.QA_FIRST_ID}"]`).click();
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Ana Reyes');

    const registerBox = await page.locator('.directory-register').boundingBox();
    const previewBox = await page.locator('[data-member-preview]').boundingBox();
    assert.ok(registerBox.y + registerBox.height <= previewBox.y, 'Registration above selected preview');
    assert.ok(registerBox.x >= previewBox.x, 'Registration in right column');
    assert.equal(await page.locator('.directory-row-arrow').count(), 0);
    await page.locator('[data-preview-full]').click();
    const dialog = page.locator('#record-details-dialog');
    await dialog.locator('[data-record-content] h1').waitFor();
    assert.equal(page.url(), originalUrl);
    assert.match(await dialog.textContent(), /Ana Reyes/);
    await page.screenshot({path: path.join(output, 'member-record-dialog.png')});
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(), false);
    assert.equal(await page.locator('[data-preview-full]').evaluate(n => n === document.activeElement), true);
    await page.locator('[data-preview-edit]').click();
    await page.getByRole('heading', {name: 'Update member record'}).waitFor();
    assert.equal(await page.locator('.onsite-section').count() >= 6, true);
    await page.screenshot({path: path.join(output, 'member-update-form.png'), fullPage: false});
    await page.goto(originalUrl);
    await page.locator('[data-select-member][role=button]').first().waitFor();

    const settled = async (query, status, count, number = 1) => page.waitForFunction(({query, status, count, number}) => {
      const params = new URL(location.href).searchParams;
      const results = document.querySelector('[data-directory-results]');
      return (params.get('q') || '') === query && params.get('status') === status &&
        Number(params.get('page') || 1) === number && results?.getAttribute('aria-busy') !== 'true' &&
        Number(results?.dataset.resultCount) === count;
    }, {query, status, count, number});
    const search = page.locator('#directory-search');
    const status = page.locator('#directory-status');
    await search.fill('Xena');
    await settled('Xena', 'active', 1);
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Xena Cruz');
    assert.equal(await search.evaluate(node => node === document.activeElement), true);
    await search.fill('TEST-2026-003');
    await settled('TEST-2026-003', 'active', 1);
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Cora Cruz');
    await search.fill('record-that-does-not-exist');
    await settled('record-that-does-not-exist', 'active', 0);
    assert.equal(await page.getByRole('heading', {name: 'No records found'}).isVisible(), true);
    assert.equal(await page.locator('[data-member-preview]').count(), 0);
    await page.locator('.directory-empty [data-clear-directory-filters]').click();
    await settled('', '', 25);
    await status.selectOption('inactive');
    await settled('', 'inactive', 3);
    assert.equal(await page.locator('[data-preview-status]').textContent(), 'Inactive');
    await status.selectOption('archived');
    await settled('', 'archived', 1);
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Zoe Garcia');
    assert.equal(await page.locator('[data-preview-edit]').isVisible(), false);
    await status.selectOption('review');
    await settled('', 'review', 1);
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Cora Cruz');
    assert.equal(await page.locator('[data-preview-status]').textContent(), 'Active');
    assert.equal(await page.locator('[data-preview-review]').isVisible(), true);
    await status.selectOption('');
    await settled('', '', 25);
    await page.locator('[data-directory-page]').filter({hasText: 'Next'}).click();
    await settled('', '', 25, 2);
    assert.equal(await page.locator('[data-select-member]').count(), 5);
    await page.goBack();
    await settled('', '', 25, 1);
    assert.equal(await page.locator('[data-select-member]').count(), 20);

    // Rapid typing must not replace a later result with a stale request.
    await search.fill('Ana');
    await search.fill('Ben');
    await settled('Ben', '', 1);
    assert.equal(await page.locator('[data-preview-name]').textContent(), 'Ben Santos');
    await page.locator('form [data-clear-directory-filters]').click();
    await settled('', '', 25);

    for (const theme of ['dark', 'light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for (const width of [1600, 1280, 1024, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        await page.evaluate(async () => {
          scrollTo({top: 0, behavior: 'instant'});
          await document.fonts.ready;
          await Promise.all(document.getAnimations().filter(animation => Number.isFinite(animation.effect.getComputedTiming().endTime)).map(animation => animation.finished.catch(() => {})));
        });
        const layout = await page.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
          return {overflow: document.documentElement.scrollWidth > innerWidth + 1,
            duplicates: ids.filter((id, index) => ids.indexOf(id) !== index)};
        });
        assert.equal(layout.overflow, false, `${theme} ${width}px page overflow`);
        assert.deepEqual(layout.duplicates, []);
        checks.push({theme, width});
        if ([1600, 390].includes(width)) await page.screenshot({path: path.join(output, `directory-${theme}-${width}.png`), fullPage: false});
      }
      await page.setViewportSize({width: 1600, height: 1000});
      await page.locator('[data-select-member]').first().click();
      const top = await page.locator('[data-directory-results]').evaluate(node => node.getBoundingClientRect().top + scrollY + 250);
      await page.evaluate(top => scrollTo({top, behavior: 'instant'}), top);
      await page.evaluate(() => new Promise(requestAnimationFrame));
      const before = await page.locator('[data-member-preview]').boundingBox();
      await page.evaluate(() => scrollBy({top: 300, behavior: 'instant'}));
      await page.evaluate(() => new Promise(requestAnimationFrame));
      const after = await page.locator('[data-member-preview]').boundingBox();
      assert.ok(Math.abs(after.y - before.y) < 1, `${theme}: member preview is not sticky`);
      assert.ok(after.y >= 76 && after.y + after.height <= 1000);
      await page.screenshot({path: path.join(output, `directory-sticky-${theme}.png`)});
    }

    await page.setViewportSize({width: 390, height: 900});
    await page.locator('[data-select-member]').nth(1).click();
    assert.equal(await page.locator('[data-preview-name]').evaluate(node => node === document.activeElement), true);
    const preview = await page.locator('[data-member-preview]').boundingBox();
    assert.ok(preview.y >= 0 && preview.y + preview.height <= 900);
    await page.screenshot({path: path.join(output, 'directory-mobile-selected.png')});
    await page.evaluate(() => { document.documentElement.dataset.text = 'largest'; document.documentElement.dataset.contrast = 'true'; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.emulateMedia({forcedColors: 'active'});
    assert.equal(await page.locator('[data-preview-full]').isVisible(), true);

    const fallback = await browser.newContext({javaScriptEnabled: false, viewport: {width: 1280, height: 900}});
    await fallback.addCookies([cookie]);
    const plain = await fallback.newPage();
    await plain.goto(url + '?q=Zoe&status=archived');
    assert.equal(await plain.locator('[data-select-member]').count(), 1);
    assert.equal(await plain.locator('[data-select-member]').getAttribute('role'), null);
    const fullRecord = await plain.locator('[data-select-member]').getAttribute('href');
    await plain.locator('[data-select-member]').click();
    assert.equal(new URL(plain.url()).pathname, fullRecord);
    await fallback.close();
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({checks, errors,
      workflow: 'Live full-registry search, filters, pagination/back, local selection, permission-aware actions and JavaScript-disabled fallback',
      accessibility: 'Keyboard selection, mobile preview focus, largest text, high contrast, forced colors and reduced motion',
      stickyPreview: 'Verified in both themes'}, null, 2));
    console.log(`PASS: ${checks.length} responsive checks; live search, status/review/archived filters, pagination, keyboard/mobile selection, sticky preview and no-JavaScript fallback.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
