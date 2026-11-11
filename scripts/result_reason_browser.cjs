/* Intercept all navigation and submissions; only local static GETs reach the app. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const {scan} = require('./admin_palette_browser.cjs');
const base = 'http://127.0.0.1:8013', fixtures = path.resolve('.local/result-reason-synthetic');
const output = path.resolve('docs/result-selection-reason-2026-11-10');
const manifest = JSON.parse(fs.readFileSync(path.join(fixtures, 'manifest.json'), 'utf8'));
fs.mkdirSync(output, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
  const errors = [], checks = [], findings = [];
  let responseFile = 'stale.html', lastPost = '', postCount = 0;
  const handleRoute = route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin === base && url.pathname === manifest.preview && request.method() === 'POST') {
      lastPost = request.postData(); postCount++;
      return route.fulfill({contentType: 'text/html; charset=utf-8', body: fs.readFileSync(path.join(fixtures, responseFile))});
    }
    if (request.method() !== 'GET') return route.abort();
    if (url.origin === base && url.pathname === manifest.preview) {
      return route.fulfill({contentType: 'text/html; charset=utf-8', body: fs.readFileSync(path.join(fixtures, 'preview.html'))});
    }
    if (url.origin === base && url.pathname + url.search === manifest.public) {
      return route.fulfill({contentType: 'text/html; charset=utf-8', body: fs.readFileSync(path.join(fixtures, 'public.html'))});
    }
    if (url.origin === base && url.pathname.startsWith('/static/')) return route.continue();
    if (url.hostname === 'cdn.tailwindcss.com') return route.fulfill({contentType: 'text/javascript', body: ''});
    return route.fulfill({status: 404, body: 'Outside synthetic fixtures'});
  };
  await context.route('**/*', handleRoute);
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const dialog = page.locator('#program-results-dialog'), reason = dialog.locator('[data-selection-reason]');
  const publish = dialog.locator('[data-publish-results]');
  try {
    for (const mode of ['light', 'dark', 'contrast-light', 'contrast-dark']) for (const width of [1440, 1000, 768, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      await page.goto(base + manifest.preview);
      await page.waitForSelector('#program-results-dialog[open]');
      await page.evaluate(mode => {
        document.documentElement.dataset.dashboardTheme = mode.endsWith('dark') ? 'dark' : 'light';
        document.documentElement.dataset.contrast = String(mode.startsWith('contrast'));
      }, mode);
      assert(await publish.isDisabled(), 'Blank reason must disable publication');
      await reason.fill('   ');
      assert(await publish.isDisabled(), 'Whitespace must disable publication');
      await reason.fill(manifest.reason);
      assert(await publish.isEnabled());
      assert.equal(await reason.evaluate(el => el.form.id), 'generate-results-form');
      assert.equal(await reason.evaluate(el => new FormData(el.form).get('selection_reason')), manifest.reason);
      const layout = await dialog.evaluate(el => {
        const cards = [...el.querySelectorAll('.results-pool-card')].map(card => card.getBoundingClientRect());
        return {width: el.getBoundingClientRect().width,
          sameRow: Math.abs(cards[0].top - cards[1].top) < 2,
          bodyOverflow: el.querySelector('.results-dialog-body').scrollWidth > el.querySelector('.results-dialog-body').clientWidth + 1,
          pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
          tableOverflow: [...el.querySelectorAll('.results-pool-table-wrap')].some(table => table.scrollWidth > table.clientWidth + 1)};
      });
      assert(layout.width <= 1061 && layout.width < width, 'Popup width stays bounded');
      assert.equal(layout.sameRow, width >= 850, 'Responsive columns');
      assert(!layout.bodyOverflow && !layout.pageOverflow && !layout.tableOverflow, 'No horizontal clipping');
      const contrast = await scan(page);
      if (contrast.low.length) findings.push({mode, width, ...contrast});
      checks.push({mode, width, ...layout, checkedText: contrast.checked});
      if (width === 1440 || width === 390) {
        await dialog.locator('.results-dialog-body').evaluate(el => { el.scrollTop = 0; });
        await dialog.screenshot({path: path.join(output, `${mode}-${width}.png`)});
        if (width === 1440) {
          await reason.scrollIntoViewIfNeeded();
          await dialog.screenshot({path: path.join(output, `${mode}-reason.png`)});
        }
      }
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.goto(base + manifest.preview);
    await page.waitForSelector('#program-results-dialog[open]');
    await dialog.locator('[data-results-search]').fill('Andrea');
    assert.equal(await dialog.locator('[data-results-applicant]:not([hidden])').count(), 1);
    assert.equal(await dialog.locator('[data-results-selection]:not([hidden])').count(), 1);
    await dialog.locator('[data-results-search]').fill('');
    await dialog.locator('[data-results-filter="selected"]').click();
    assert.equal(await dialog.locator('[data-results-applicant]:not([hidden])').count(), 1);
    await reason.fill(manifest.reason);
    await publish.click();
    await dialog.getByText('The recorded results changed. Review the refreshed list before publishing.').waitFor();
    assert(lastPost.includes('name="selection_reason"') && lastPost.includes(manifest.reason), 'Associated textarea sent in POST');
    assert.equal(await reason.inputValue(), manifest.reason, 'Stale error retains explanation');
    assert(await publish.isEnabled(), 'Refreshed preview requires another click');
    assert.equal(postCount, 1);
    responseFile = 'errors.html';
    await publish.click();
    await reason.locator('..').getByText('Explain why these members were selected before publishing the results.', {exact: true}).waitFor();
    assert(await publish.isDisabled());
    assert.equal(await reason.evaluate(el => el.tabIndex), 0, 'Invalid reason remains in keyboard order');
    await reason.fill(manifest.reason);
    responseFile = 'published.html';
    await publish.click();
    await dialog.getByText('Program results published.', {exact: true}).waitFor();
    assert.equal(await reason.inputValue(), manifest.reason);
    await page.keyboard.press('Escape');
    assert(!(await dialog.isVisible()));
    await page.goto(base + manifest.public);
    await page.getByRole('heading', {name: 'Why these members were selected'}).waitFor();
    assert((await page.locator('body').innerText()).includes(manifest.reason));
    const nojs = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 1000}});
    await nojs.route('**/*', handleRoute);
    const fallback = await nojs.newPage();
    await fallback.goto(base + manifest.preview);
    assert(await fallback.locator('[data-selection-reason]').isVisible());
    assert.equal(await fallback.locator('[data-selection-reason]').getAttribute('required'), '');
    await nojs.close();
    assert.deepEqual(errors, [], 'No browser script errors');
    fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify({checks, errors, contrastFindings: findings, interceptedPosts: postCount}, null, 2));
    console.log(JSON.stringify({responsiveChecks: checks.length, browserErrors: errors.length, contrastFindings: findings.length, interceptedPosts: postCount}));
    if (findings.length) console.log(JSON.stringify(findings));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
