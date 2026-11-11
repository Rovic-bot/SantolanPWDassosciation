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
    const lab = '/ewaf/development/';
    const history = `${lab}program/${process.env.QA_PROGRAM}/`;
    async function goto(route) {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
    }
    await goto(lab);
    assert.equal(await page.locator('select[name^="pair_"]').count(), 6);
    await page.getByLabel('Human selection demonstration').selectOption('DEMO-B');
    await page.getByRole('button', {name: 'Recalculate fictional example', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.ok((await page.locator('main').innerText()).includes('Human choice in this example: yes'));
    const pending = page.getByLabel('Keep fictional DEMO-C awaiting review');
    await page.getByLabel('Human selection demonstration').selectOption('');
    await pending.focus();
    await page.keyboard.press('Space');
    assert.ok(await pending.isChecked());
    await page.getByRole('button', {name: 'Recalculate fictional example', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.ok((await page.locator('main').innerText()).includes('ELIGIBILITY_REVIEW_PENDING'));
    assert.ok(!(await page.locator('main').innerText()).includes('Illustrative score:'));
    for (let version = 1; version <= 2; version++) {
      await goto(history);
      await page.getByLabel('Development recalculation reason').fill(`Fictional browser version ${version}`);
      await page.getByRole('button', {name: 'Calculate a new fictional version', exact: true}).click();
      await page.waitForLoadState('networkidle');
      assert.ok((await page.locator('main').innerText()).includes('current at this inspection'));
    }
    assert.ok((await page.locator('main').innerText()).includes('historical only'));
    for (const route of [lab, history]) {
      await goto(route);
      assert.equal(await page.locator('main h1').count(), 1);
      if (route === history) {
        await page.locator('main details summary').first().focus();
        await page.keyboard.press('Enter');
        assert.ok(await page.locator('main details').first().evaluate(el => el.open));
      }
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width, height: 900});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${route}: ${width}`);
      }
      for (const control of await page.locator('main input:not([type="hidden"]), main select, main textarea').all()) {
        assert.ok(await control.evaluate(el => el.labels && el.labels.length > 0), route);
      }
      assert.equal(await page.locator('[name="weights"], [name="score"], [name="rank"], input[type="file"]').count(), 0);
      assert.ok((await page.locator('main').innerText()).includes('Fictional') || route === lab);
    }
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'stage8-history.png'), fullPage: true});
    await goto(lab);
    await page.setViewportSize({width: 390, height: 900});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'stage8-mobile.png'), fullPage: true});
    await page.setViewportSize({width: 1440, height: 1000});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'stage8-desktop.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('Stage 8 browser: 2 private pages, 4 widths, explicit labels, keyboard checkbox, fictional selection, incomplete-pool blocking, 2 actual versioned calculations, retained history, no editable scores/ranks, and no page errors passed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
