const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, reducedMotion: 'reduce'});
    const base = process.env.QA_URL;
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: base}]);
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
      ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + process.env.QA_SETTINGS);
    const root = page.locator('.association-email-settings');
    assert.equal(await root.locator('input[type=password][name=gmail_app_password]').count(), 1);
    assert.equal(await root.locator('[name=reason]').count(), 0);
    await page.getByLabel('Association Email').fill('updated.association@example.invalid');
    await page.getByLabel('Gmail app password', {exact: true}).fill('abcd efgh ijkl mnop');
    await page.getByRole('button', {name: 'Save Changes', exact: true}).click();
    await page.getByText('Association email connection saved. No email was sent by this check.', {exact: true}).waitFor();
    assert.equal(await page.getByLabel('Gmail app password', {exact: true}).inputValue(), '');
    assert.equal((await page.content()).includes('abcdefghijklmnop'), false);
    assert.equal(await root.locator('.email-history-entry').count(), 2);
    for (const theme of ['dark', 'light']) {
      await page.waitForLoadState('networkidle');
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) {
        await page.getByRole('button', {name: 'Display preferences', exact: true}).click();
        await page.locator('[data-preference="dark"]').setChecked(theme === 'dark');
        await page.getByRole('button', {name: 'Close display preferences', exact: true}).click();
      }
      assert.equal(await page.locator('html').getAttribute('data-dashboard-theme'), theme);
      for (const width of [1600, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${theme} ${width} overflow`);
        await page.screenshot({path: path.join(process.env.QA_OUTPUT, `${theme}-${width}.png`), fullPage: true});
      }
    }
    assert.deepEqual(errors, []);
    console.log('Gmail setup, cleared password, two history entries, and eight theme/viewport checks passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
