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
    const base = `/ewaf/configurations/${process.env.QA_PROGRAM}/`;
    async function goto(route) {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
    }
    async function confirmAndSubmit(label) {
      await page.getByLabel('Review explanation').fill('Synthetic G18-A browser review');
      const confirm = page.getByLabel('I confirm that this records a review finding', {exact: false});
      await confirm.focus();
      await page.keyboard.press('Space');
      assert.ok(await confirm.isChecked());
      await page.getByRole('button', {name: label, exact: true}).click();
      await page.waitForURL(process.env.QA_URL + base);
    }
    await goto(base + 'draft/');
    const comparisons = page.locator('input[name^="pair_"]');
    assert.equal(await comparisons.count(), 10);
    for (const field of await comparisons.all()) {
      assert.equal(await field.inputValue(), '');
      await field.fill('1');
    }
    await confirmAndSubmit('Record configuration draft');
    await goto(base + 'validate/');
    await confirmAndSubmit('Retain reference validation');
    assert.ok((await page.locator('main').innerText()).includes('PASSED'));
    assert.deepEqual(await page.locator('[data-diagnostic-weights] dt').allTextContents(), ['SI', 'ES', 'PA', 'ND', 'PR']);
    await goto(base + 'review/');
    await page.getByLabel(/^Finding:?$/).selectOption('REVIEWED');
    await confirmAndSubmit('Record configuration review');
    await goto(base + 'authority/');
    await page.getByLabel('Documentary authority reference').fill('Synthetic browser reference');
    await page.getByLabel('Stated scope').fill('Synthetic AHP judgments only');
    await page.getByLabel('I attest that I reviewed the cited document', {exact: false}).check();
    await confirmAndSubmit('Record non-effective authority evidence');
    assert.ok((await page.locator('main').innerText()).includes('RECORDED_NON_EFFECTIVE'));
    assert.ok((await page.locator('main').innerText()).includes('PROCESSING_GATE_UNAVAILABLE'));
    const routes = ['/ewaf/configurations/', base + 'policy-review/', base, base + 'draft/', base + 'validate/', base + 'review/', base + 'authority/', base + 'history/'];
    for (const route of routes) {
      await goto(route);
      assert.equal(await page.locator('main h1').count(), 1);
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width, height: 900});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${route}: ${width}`);
      }
      for (const control of await page.locator('main input:not([type="hidden"]), main select, main textarea').all()) {
        assert.ok(await control.evaluate(el => el.labels && el.labels.length > 0), route);
      }
      assert.equal(await page.locator('[name="weights"], [name="score"], [name="rank"], input[type="file"]').count(), 0);
    }
    await goto(base + 'policy-review/');
    assert.equal(await page.locator('[data-policy-item]').count(), 12);
    assert.equal(await page.locator('main form').count(), 0);
    assert.ok((await page.locator('main').innerText()).includes('Association policy decisions remain pending'));
    await page.getByRole('link', {name: 'Configuration diagnostics', exact: true}).first().focus();
    await page.keyboard.press('Enter');
    await page.waitForURL(process.env.QA_URL + base);
    await page.getByRole('link', {name: 'Review computation references and pending policies'}).click();
    await page.waitForURL(process.env.QA_URL + base + 'policy-review/');
    await page.setViewportSize({width: 390, height: 900});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'g18-policy-mobile.png'), fullPage: true});
    await page.setViewportSize({width: 1440, height: 1000});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'g18-policy-desktop.png'), fullPage: true});
    await goto(base + 'draft/');
    await page.setViewportSize({width: 390, height: 900});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'g18-draft-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('G18-A browser: 8 pages, 4 widths, labels, keyboard confirmation, 4 actual POST workflows, no preset judgments, non-effective authority and blocked processing passed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
