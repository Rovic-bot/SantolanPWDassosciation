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
    const workspace = `/ewaf/development/four/${process.env.QA_PROGRAM}/`;
    const history = `/ewaf/development/program/${process.env.QA_PROGRAM}/`;
    async function goto(route) {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
    }
    await goto(workspace);
    assert.equal(await page.locator('select[name^="pair_"]').count(), 6);
    await page.getByLabel('SI compared with ES').selectOption('3');
    await page.getByLabel('Fictional configuration change reason').fill('Fictional guided AHP review; no Association approval.');
    await page.getByRole('button', {name: 'Retain fictional four-criterion configuration', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.ok((await page.locator('main').innerText()).includes('BLOCKED_POLICY'));
    for (let version = 1; version <= 2; version++) {
      await goto(history);
      await page.getByLabel('Development recalculation reason').fill(`Fictional verified four-criterion version ${version}`);
      await page.getByRole('button', {name: 'Calculate a new fictional version', exact: true}).click();
      await page.waitForLoadState('networkidle');
      assert.ok((await page.locator('main').innerText()).includes('current at this inspection'));
    }
    assert.ok((await page.locator('main').innerText()).includes('historical only'));
    await page.locator('main details summary').first().focus();
    await page.keyboard.press('Enter');
    assert.ok(await page.locator('main details').first().evaluate(el => el.open));
    assert.equal(await page.locator('main details').first().locator('dt').count(), 4);
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'four-history.png'), fullPage: true});
    await goto(workspace);
    await page.getByLabel('Human demonstration decision').selectOption('SELECT_FOR_DEMONSTRATION');
    await page.getByLabel('Human decision reason').fill('Fictional functional need and evidence reviewed; this is a separate human choice.');
    await page.getByRole('button', {name: 'Demonstrate reasoned human decision', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.ok((await page.locator('main').innerText()).includes('Selected in demonstration: yes. Actually assisted: no. Saved: no.'));
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({width, height: 900});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `workspace ${width}`);
    }
    assert.equal(await page.locator('main h1').count(), 1);
    for (const control of await page.locator('main input:not([type="hidden"]), main select, main textarea').all()) {
      assert.ok(await control.evaluate(el => el.labels && el.labels.length > 0));
    }
    assert.equal(await page.locator('[name="score"], [name="rank"], [name="weights"]').count(), 0);
    await page.setViewportSize({width: 390, height: 900});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'four-mobile.png'), fullPage: true});
    await page.setViewportSize({width: 1440, height: 1000});
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'four-desktop.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('Four-criterion browser passed: verified fictional applications, six guided comparisons, retained configuration, two calculations, four traces per result, immutable predecessor history, reasoned transient human choice, no assistance effect, labels, keyboard disclosure, four responsive widths, no page errors.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
