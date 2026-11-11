const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.QA_URL + process.env.QA_ROUTE);
    const [a, b] = JSON.parse(process.env.QA_APPLICANTS);
    const first = page.locator(`#receipt-${a}`), added = page.locator(`#receipt-${b}`);
    if (process.env.QA_PHASE === 'before') {
      assert(await first.locator('button.receipt-button').isEnabled());
      assert(await added.locator('button.receipt-button').isDisabled());
      assert.match(await added.innerText(), /Publish this selected member in Announcements first/);
      for (const width of [1440, 390]) {
        await page.setViewportSize({width, height: 1000});
        await added.locator('.receipt-publication-note').scrollIntoViewIfNeeded();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        const button = await added.locator('button.receipt-button').boundingBox();
        const note = await added.locator('.receipt-publication-note').boundingBox();
        assert(note.y >= button.y + button.height, 'Publication explanation sits below the button');
        assert(note.x >= 0 && note.x + note.width <= width, 'Publication explanation stays visible');
        await page.screenshot({path: path.join(process.env.QA_OUTPUT, `waiting-for-publication-${width}.png`)});
      }
      await first.locator('.receipt-action-form button').click();
      await first.locator('.receipt-action .receipt-recorded').waitFor();
      assert(await added.locator('button.receipt-button').isDisabled());
    } else {
      assert.equal(await first.locator('.receipt-action .receipt-recorded').innerText(), 'Recorded');
      assert(await added.locator('.receipt-action-form button').isEnabled());
      await added.locator('.receipt-action-form button').click();
      await added.locator('.receipt-action .receipt-recorded').waitFor();
      assert.equal(await page.locator('.receipt-action .receipt-recorded').count(), 2);
      await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'published-and-recorded.png')});
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
