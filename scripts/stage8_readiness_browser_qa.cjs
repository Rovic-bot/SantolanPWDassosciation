const path = require('path');
const assert = require('assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || runtime);
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const workspace = `/ewaf/development/four/${process.env.QA_PROGRAM}/`;
    const history = `/ewaf/development/program/${process.env.QA_PROGRAM}/`;
    async function goto(route) {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
    }
    async function screenshot(name) {
      await page.screenshot({path: path.join(process.env.QA_OUTPUT, name)});
    }
    await goto(workspace);
    assert.ok((await page.locator('main').innerText()).includes('All 5 retained applications'));
    assert.equal(await page.locator('main table tbody tr').count(), 5);
    await screenshot('readiness-inventory.png');
    for (let version = 1; version <= 2; version++) {
      await goto(history);
      await page.getByLabel('Development recalculation reason').fill(`Fictional complete verified pool revision ${version}; preserve history.`);
      await page.getByRole('button', {name: 'Calculate a new fictional version', exact: true}).click();
      await page.waitForLoadState('networkidle');
      assert.ok((await page.locator('main').innerText()).includes('current at this inspection'));
    }
    const table = page.locator('[data-comparison-run]').first();
    const scores = await table.locator('[data-score]').evaluateAll(cells => cells.map(c => c.dataset.score));
    assert.equal(scores.length, 4);
    assert.ok((await page.locator('main').innerText()).includes('is retained outside this cutoff and was not scored'));
    assert.equal(scores[0], scores[1]);
    assert.ok(Number(scores[1]) > Number(scores[2]) && Number(scores[2]) > Number(scores[3]));
    assert.equal(await table.locator('tbody tr').first().locator('td').last().innerText(), '2');
    await page.getByRole('heading', {name: 'Immutable calculation history', exact: true}).scrollIntoViewIfNeeded();
    await screenshot('readiness-comparison.png');
    const detail = page.locator('main details').first();
    await detail.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert.ok(await detail.evaluate(el => el.open));
    assert.deepEqual(await detail.locator('dt').allTextContents(), ['SI', 'ES', 'PA', 'ND']);
    await detail.scrollIntoViewIfNeeded();
    await screenshot('readiness-calculation.png');
    await page.locator('main section').last().scrollIntoViewIfNeeded();
    await screenshot('readiness-history.png');
    await goto(workspace);
    await page.getByLabel('Human demonstration decision').selectOption('SELECT_FOR_DEMONSTRATION');
    await page.getByLabel('Human decision reason').fill('Fictional verified functional need reviewed by an officer. Calculation does not automatically select a beneficiary.');
    await page.getByRole('button', {name: 'Record fictional human decision', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('[aria-label="Saved fictional human decisions"] article').count(), 1);
    await page.getByLabel('Human demonstration decision').selectOption('DEFER_FOR_REVIEW');
    await page.getByLabel('Human decision reason').fill('Fictional follow-up review requested; preserve the previous human choice and all calculated scores.');
    await page.getByRole('button', {name: 'Record fictional human decision', exact: true}).click();
    await page.waitForLoadState('networkidle');
    const saved = page.locator('[aria-label="Saved fictional human decisions"]');
    assert.equal(await saved.locator('article').count(), 2);
    assert.ok((await saved.innerText()).includes('Revision 2'));
    assert.ok((await saved.innerText()).includes('Saved: yes. Actually assisted: no.'));
    await saved.locator('summary').first().click();
    await saved.scrollIntoViewIfNeeded();
    await screenshot('readiness-decision.png');
    for (const route of [workspace, history]) {
      await goto(route);
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width, height: 1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${route} ${width}`);
      }
      assert.equal(await page.locator('main h1').count(), 1);
      assert.equal(await page.locator('[name="score"], [name="rank"], [name="weights"]').count(), 0);
      for (const control of await page.locator('main input:not([type="hidden"]), main select, main textarea').all()) {
        assert.ok(await control.evaluate(el => el.labels && el.labels.length));
      }
    }
    await page.setViewportSize({width: 390, height: 1000});
    await page.locator('[data-comparison-run]').first().scrollIntoViewIfNeeded();
    await screenshot('readiness-mobile.png');
    assert.deepEqual(errors, []);
    console.log('Readiness browser passed: five retained applications, four verified results, distinct score order and exact ties, SI/ES/PA/ND traces, two immutable runs, two saved reasoned human revisions with audits, no assistance effect, no-store, labels, keyboard and four responsive widths.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
