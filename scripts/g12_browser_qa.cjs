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
    const base = `/ewaf/evidence/${process.env.QA_APPLICATION}/`;
    const routes = ['/ewaf/evidence/', base, base + 'history/', base + 'review/ND/', base + 'review/PR/', `/ewaf/evidence/policy/${process.env.QA_PROGRAM}/`];
    for (const route of routes) {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200, route);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
      assert.equal(await page.locator('main h1').count(), 1);
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width, height: 900});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${route}: ${width}`);
      }
      for (const control of await page.locator('main input:not([type="hidden"]), main select, main textarea').all()) {
        assert.ok(await control.evaluate(el => el.labels && el.labels.length > 0), `${route}: missing label`);
      }
      assert.equal(await page.locator('[name="score"], [name="rank"], [name="budget"], input[type="file"]').count(), 0);
    }
    await page.goto(process.env.QA_URL + base + 'review/PR/');
    await page.getByLabel(/^State:?$/).selectOption('VERIFIED');
    await page.getByLabel(/^Value:?$/).fill('relevant');
    await page.getByLabel('Review explanation').fill('Synthetic favorable category without item findings');
    await page.getByLabel('I confirm that this records a review finding', {exact: false}).check();
    await page.getByLabel('I attest that each relevance finding', {exact: false}).check();
    await page.getByRole('button', {name: 'Append evidence finding'}).click();
    assert.ok((await page.locator('main').innerText()).includes('PR_FINDINGS_INCOMPLETE'));
    await page.goto(process.env.QA_URL + base + 'review/ND/');
    const confirm = page.getByLabel('I confirm that this records a review finding', {exact: false});
    await confirm.focus();
    await page.keyboard.press('Space');
    assert.ok(await confirm.isChecked());
    await page.getByLabel(/^State:?$/).selectOption('NEEDS_REVIEW');
    await page.getByLabel('Review explanation').fill('Synthetic browser disputed finding');
    await page.getByLabel('This finding is disputed').check();
    await page.getByRole('button', {name: 'Append evidence finding'}).click();
    await page.waitForURL(process.env.QA_URL + base);
    assert.ok((await page.locator('main').innerText()).includes('EVIDENCE_DISPUTED'));
    assert.ok((await page.locator('main').innerText()).includes('PROCESSING_GATE_UNAVAILABLE'));
    await page.getByLabel('Review explanation').fill('Synthetic browser diagnostic retention');
    await page.getByLabel('I confirm that this records a review finding', {exact: false}).check();
    await page.getByRole('button', {name: 'Retain readiness snapshot'}).click();
    await page.waitForURL(process.env.QA_URL + base + 'history/');
    assert.ok((await page.locator('main').innerText()).includes('Revision 2'));
    assert.ok((await page.locator('main').innerText()).includes('Synthetic browser diagnostic retention'));
    await page.setViewportSize({width: 390, height: 900});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'g12-history-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('G12 browser: 6 private pages, 4 widths, labels, keyboard confirmation, rejected incomplete PR verification, disputed review and snapshot POST flows passed.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exit(1);});
