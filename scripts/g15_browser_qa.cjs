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
    const policy = `/ewaf/diagnostics/policy/${process.env.QA_PROGRAM}/`;
    const readiness = `/ewaf/diagnostics/application/${process.env.QA_APPLICATION}/`;
    async function goto(route) {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
    }
    async function submit(label, destination) {
      await page.getByLabel('Review explanation').fill('Synthetic G15 browser diagnostic');
      const confirm = page.getByLabel('I confirm that this records a review finding', {exact: false});
      await confirm.focus();
      await page.keyboard.press('Space');
      assert.ok(await confirm.isChecked());
      await page.getByRole('button', {name: label, exact: true}).click();
      await page.waitForURL(process.env.QA_URL + destination);
    }
    await goto(policy);
    const proposed = page.getByLabel('Scoring-policy proposal (JSON)', {exact: false});
    assert.equal(await proposed.inputValue(), '');
    await proposed.fill(JSON.stringify({criteria: {SI: {}, ES: {}, PA: {}, ND: {}, PR: {}}}));
    await submit('Record policy proposal', policy);
    await goto(readiness);
    assert.ok((await page.locator('main').innerText()).includes('PROCESSING_GATE_UNAVAILABLE'));
    await submit('Retain readiness diagnostic', readiness + 'history/');
    assert.ok((await page.locator('main').innerText()).includes('Validated'));
    for (const route of ['/ewaf/diagnostics/', policy, readiness, readiness + 'history/']) {
      await goto(route);
      assert.equal(await page.locator('main h1').count(), 1);
      assert.ok((await page.locator('main').innerText()).includes('DIAGNOSTIC ONLY'));
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width, height: 900});
        const overflow = await page.evaluate(() => ({bad: document.documentElement.scrollWidth > innerWidth + 1,
          elements: [...document.querySelectorAll('main *')].filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 5).map(el => el.tagName + ':' + el.className)}));
        assert.equal(overflow.bad, false, `${route}: ${width}: ${overflow.elements.join(', ')}`);
      }
      for (const control of await page.locator('main input:not([type="hidden"]), main select, main textarea').all()) {
        assert.ok(await control.evaluate(el => el.labels && el.labels.length > 0), route);
      }
      assert.equal(await page.locator('[name="weights"], [name="score"], [name="rank"], input[type="file"]').count(), 0);
    }
    await goto(readiness);
    await page.setViewportSize({width: 390, height: 900});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'g15-readiness-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('G15 browser: 4 pages, 4 widths, labels, keyboard confirmation, 2 POST workflows, no preset rules, no applicant scores, no JavaScript errors.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
