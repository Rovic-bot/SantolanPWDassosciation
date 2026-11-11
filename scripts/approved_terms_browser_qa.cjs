const path = require('path');
const assert = require('assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || runtime);

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({reducedMotion: 'reduce'});
    await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const base = `/programs/manage/${process.env.QA_PROGRAM}/terms/`;
    for (const route of ['/programs/manage/pdao-readiness/', base, base + process.env.QA_REVISION + '/']) {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width, height: 900});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, route + ': ' + width);
      }
    }
    assert.equal(await page.getByRole('heading', {name: 'Immutable recorded terms', exact: true}).isVisible(), true);
    assert.equal(await page.locator('form[method="post"] #id_confirmed').count(), 0);
    await page.goto(process.env.QA_URL + base);
    assert.equal(await page.locator('input[type="file"], [name="budget"]').count(), 0);
    const confirmation = page.getByLabel('I reviewed the displayed terms.', {exact: false});
    await confirmation.focus();
    await page.keyboard.press('Space');
    assert.equal(await confirmation.isChecked(), true);
    assert.equal(await page.getByRole('button', {name: 'Record reviewed action'}).isVisible(), true);
    assert.ok((await page.locator('main').innerText()).includes('Philippine time'));
    await page.setViewportSize({width: 390, height: 900});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'synthetic-terms-review.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('Approved terms browser QA passed: private readiness/review/history, 4 widths, keyboard confirmation, labels, no uploads/budget fields, no JavaScript errors.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exit(1);});
