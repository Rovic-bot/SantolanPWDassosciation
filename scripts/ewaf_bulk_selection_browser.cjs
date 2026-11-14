/* Fictional checked selections on an isolated Django test server. */
const path = require('path'), fs = require('fs'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  assert(process.env.FEATURE_ARTIFACT_DIR, 'Disposable feature test launcher required');
  const origin = new URL(process.env.QA_URL).origin;
  assert(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname));
  assert(!['8000', '8012'].includes(new URL(origin).port));
  const output = path.join(process.env.FEATURE_ARTIFACT_DIR, 'bulk-selection');
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1536, height: 1050}, reducedMotion: 'reduce'});
    context.setDefaultTimeout(10000);
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/');
    await page.locator('[name=username]').fill(process.env.QA_USERNAME);
    await page.locator('[name=password]').fill(process.env.QA_PASSWORD);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    await page.goto(`${origin}/ewaf/programs/${process.env.QA_PROGRAM}/`);
    console.log('Opened synthetic ranking');
    const boxes = page.locator('[data-bulk-application]:not(:disabled)');
    const submit = page.locator('[data-bulk-submit]'), all = page.locator('[data-bulk-select-all]');
    assert.equal(await boxes.count(), 3);
    assert(await submit.isDisabled());
    await all.check();
    assert.equal(await page.locator('[data-bulk-application]:checked').count(), 3);
    assert.equal(await page.locator('[data-bulk-count]').innerText(), '3');
    assert(await submit.isDisabled());
    assert.match(await page.locator('[data-bulk-feedback]').innerText(), /only 2 are available/);
    await all.uncheck();
    const details = page.locator('[data-bulk-tie]');
    assert.equal(await details.count(), 2);
    const initialUrl = page.url(), wasOpen = await details.first().evaluate(element => element.open);
    await details.first().locator('summary').click();
    assert.equal(await details.first().evaluate(element => element.open), !wasOpen);
    assert.equal(page.url(), initialUrl);
    if (wasOpen) await details.first().locator('summary').click();
    await details.first().locator('label').click();
    assert(await details.first().locator('textarea').evaluate(element => document.activeElement === element));
    console.log('Capacity and tie controls passed');
    for (const detail of await details.all()) {
      const id = await detail.getAttribute('data-bulk-tie');
      await page.locator(`[data-bulk-application][value="${id}"]`).check();
      assert(await detail.locator('textarea').evaluate(element => element.required));
      await detail.locator('textarea').fill('Fictional application of the approved human tie procedure.');
    }
    assert(await all.evaluate(element => element.indeterminate));
    assert.equal(await page.locator('[data-bulk-count]').innerText(), '2');
    assert(await submit.isEnabled());
    await page.screenshot({path: path.join(output, 'checked-desktop.png'), fullPage: true});
    const scores = () => page.locator('tr[data-applicant]').evaluateAll(rows => rows.map(row => ({
      id: row.dataset.applicant, rank: row.querySelector('.ewaf-rank').innerText,
      score: row.querySelector('.ewaf-score-link strong').innerText})));
    const before = await scores();
    await submit.click({timeout: 60000});
    await page.waitForURL(url => url.hash === '#results', {timeout: 60000});
    await page.waitForLoadState('domcontentloaded');
    assert.equal(await page.locator('[data-bulk-application]:disabled').count(), 2);
    assert.equal(await boxes.count(), 1);
    assert.match(await page.locator('.ewaf-bulk-capacity').innerText(), /0 available slots/);
    assert.deepEqual(await scores(), before);
    console.log('Explicit batch POST and unchanged scores passed');
    await page.locator('#ranking-filters [name=decision]').selectOption('selected');
    await page.waitForFunction(() => document.querySelector('#ranking-body').dataset.count === '2');
    assert.equal(await boxes.count(), 0);
    assert(await all.isDisabled());
    await page.locator('#ranking-filters [name=decision]').selectOption('');
    await page.waitForFunction(() => document.querySelector('#ranking-body').dataset.count === '3');
    await all.check();
    assert.equal(await page.locator('[data-bulk-application]:checked').count(), 1);
    assert(await submit.isDisabled());
    await all.uncheck();
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(output, 'selected-mobile.png'), fullPage: true});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
    assert.deepEqual(errors, []);
    console.log('Selected-row disabling, filters and mobile layout passed');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
