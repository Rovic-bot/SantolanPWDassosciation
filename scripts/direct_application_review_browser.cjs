/* Synthetic HTML fixture; all decision requests are intercepted, never sent. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const html = fs.readFileSync(process.argv[2], 'utf8');
assert.ok(html.includes('Synthetic submitted explanation.') && html.includes('SYNTHETIC-PWD-ID'));
const routePath = html.match(/id="eligibility-decision-form" method="post" action="([^"]+)"/)[1];
const origin = 'http://127.0.0.1:8013';
const output = path.resolve(__dirname, '../docs/direct-application-review-2026-10-29');
fs.mkdirSync(output, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    const decisions = [], errors = [], blocked = [];
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin) { blocked.push(url.href); return route.abort(); }
      if (url.pathname === routePath) {
        if (request.method() === 'POST') {
          const body = request.postData() || '';
          assert.ok(body.includes('name="action"\r\n\r\nreview_decision'));
          decisions.push(body.match(/name="eligibility"\r\n\r\n([^\r]+)/)[1]);
        } else assert.equal(request.method(), 'GET');
        return route.fulfill({status: 200, contentType: 'text/html', body: html});
      }
      if (request.method() === 'GET' && url.pathname.startsWith('/static/')) return route.continue();
      if (request.method() === 'GET' && url.pathname.startsWith('/programs/photos/')) {
        return route.fulfill({status: 200, contentType: 'image/svg+xml',
          body: '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="200"><rect width="240" height="200" fill="#e2eeea"/><text x="120" y="100" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#24594e">Synthetic test photo</text></svg>'});
      }
      blocked.push(url.pathname); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + routePath, {waitUntil: 'networkidle'});
    for (const id of ['program-requirements', 'membership-review', 'disability-review', 'photo-review', 'program-fit-review']) {
      assert.equal(await page.locator('#' + id).count(), 0);
    }
    assert.equal(await page.locator('#documents').getByText('Synthetic submitted explanation.', {exact: true}).isVisible(), true);
    assert.equal(await page.locator('#decision_notes').getAttribute('required'), null);
    assert.equal(await page.locator('#documents a').filter({hasText: 'Preview'}).count(), 1);
    await page.locator('#documents').evaluate(element => scrollTo(0, element.getBoundingClientRect().top + scrollY - 25));
    await page.screenshot({path: path.join(output, 'submitted-information-desktop.png')});
    await page.locator('#eligibility').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(output, 'decision-desktop.png')});
    for (const outcome of ['eligible', 'review', 'ineligible']) {
      await page.locator(`button[name="eligibility"][value="${outcome}"]`).click();
      await page.waitForFunction(() => !document.querySelector('[data-saving]'));
      assert.equal(decisions.at(-1), outcome);
      assert.equal(await page.locator('[data-review-error]').isVisible(), false);
    }
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({width, height: 1000});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      if (width === 390) {
        await page.locator('#eligibility').scrollIntoViewIfNeeded();
        await page.screenshot({path: path.join(output, 'decision-mobile.png')});
      }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(blocked, []);
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({
      synthetic_fixture: true, separate_panels_removed: true, submission_visible: true,
      optional_remarks: true, intercepted_decisions: decisions, backend_mutations: 0,
      responsive_widths: [320, 390, 768, 1440], page_errors: errors
    }, null, 2));
    console.log('PASS: visible submission, three intercepted decision clicks, optional remarks, and four responsive widths; no backend mutations.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
