/* Only the identity-guarded disposable Django test server supplies this journey. */
const path = require('path');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const origin = new URL(process.env.QA_URL).origin;
  assert(['localhost', '127.0.0.1'].includes(new URL(origin).hostname));
  assert(!['8000', '8012'].includes(new URL(origin).port), 'Disposable test server required');
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(process.env.QA_USERNAME);
    await page.locator('[name=password]').fill(process.env.QA_PASSWORD);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/ewaf/vault/');
    for (const code of ['SES', 'HM']) {
      await page.goto(origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
      if (code === 'HM') {
        const up = page.locator('.weight-row[data-criterion="HM"] .weight-order button').first();
        for (let i = 0; i < 3; i++) await up.click();
      }
      await page.locator('#weight-' + code).evaluate(input => {
        input.value = '62.5'; input.dispatchEvent(new Event('input', {bubbles: true}));
      });
      await page.locator('#preview-weights').click();
      await page.waitForFunction(() => document.querySelector('[name=weight_review]').value &&
        !document.querySelector('button[value=LOCKED]').disabled);
      await page.locator('[name=reason]').fill('Synthetic reranking browser approval after delivered assistance.');
      await page.locator('button[value=LOCKED]').click();
      await page.waitForLoadState('networkidle');
      assert((await page.locator('main').innerText()).includes('Configuration approved.'));
      for (const [index, program] of JSON.parse(process.env.QA_PROGRAMS).entries()) {
        await page.goto(`${origin}/ewaf/programs/${program}/`, {waitUntil: 'networkidle'});
        const generate = page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true});
        assert(await generate.isEnabled(), await page.locator('main').innerText());
        await generate.click();
        await page.waitForLoadState('networkidle');
        const rows = page.locator('#results table tbody tr');
        assert.equal(await rows.count(), 12);
        assert.equal((await rows.first().locator('th a').innerText()).trim(),
          code === 'SES' ? 'Ana Testalpha' : 'Dan Testdelta');
        assert((await page.locator('.ewaf-summary').innerText()).includes('Verified'));
        if (index === 0) {
          const completed = rows.filter({hasText: 'Ben Testbravo'});
          assert((await completed.innerText()).includes('Assistance received'));
          await completed.locator('.ewaf-review-link').click();
          assert.equal(await page.locator('dialog:modal').getByRole('button', {name: 'Select for assistance', exact: true}).count(), 0);
          await page.keyboard.press('Escape');
          await page.waitForFunction(() => !document.querySelector('dialog:modal'));
        }
        const iris = (await rows.filter({hasText: 'Iris Testindia'}).locator('td').allTextContents()).slice(0, 2);
        const jiro = (await rows.filter({hasText: 'Jiro Testjuliet'}).locator('td').allTextContents()).slice(0, 2);
        assert.deepEqual(iris, jiro);
        await page.locator('#results').screenshot({path: path.join(process.env.QA_OUTPUT, `reranking-${code}-${index}.png`)});
      }
    }
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert.deepEqual(errors, []);
    console.log('PASS browser: two repeated Vault approvals, four rankings across two existing programs after delivery, full 12-member pool, current scores, exact ties, completed recipient protected, mobile layout.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
