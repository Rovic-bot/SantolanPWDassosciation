const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT;
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, reducedMotion: 'reduce', colorScheme: 'dark'});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: base}]);
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
      ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + process.env.QA_START);
    await page.evaluate(() => {
      window.keptDocument = true;
      document.addEventListener('workspace:navigated', () => { window.tabFinished = true; });
    });
    const tab = page.locator(`.workspace-module-links a[href="${process.env.QA_LIST}"]`);
    await tab.evaluate(node => { node.closest('details').open = true; });
    await tab.click();
    await page.waitForFunction(() => window.tabFinished);
    assert.equal(await page.evaluate(() => window.keptDocument), true, 'Uses actual workspace tab navigation');
    assert.equal(await page.locator('body noscript, noscript style').count(), 0, 'Fallback styles are not imported');
    const dialog = page.locator('#program-results-dialog');
    assert.equal(await dialog.isVisible(), false, 'No box below the program list');
    const open = async () => {
      await page.locator('[data-announcement-panel]:not([hidden]) [data-results-preview]').click();
      await dialog.locator('[data-results-applicant]').first().waitFor();
      assert.equal(await dialog.evaluate(node => node.matches(':modal')), true);
    };
    await open();
    for (const width of [1600, 768, 390]) {
      await page.setViewportSize({width, height: 1000});
      const box = await dialog.boundingBox();
      assert.ok(box.width <= 881 && box.width < width, 'Compact popup with margins');
      assert.ok(box.height <= 851 && box.y >= 0 && box.y + box.height <= 1001);
      assert.equal(await dialog.locator('.results-dialog-close').isVisible(), true);
      const publish = await dialog.getByRole('button', {name: 'Publish results', exact: true}).boundingBox();
      assert.ok(publish.y >= box.y && publish.y + publish.height <= box.y + box.height + 1, 'Footer remains in popup');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path: path.join(output, `preview-${width}.png`)});
    }
    await page.setViewportSize({width: 1600, height: 1000});
    await dialog.locator('[data-results-search]').fill('no-such-applicant');
    assert.equal(await dialog.locator('[data-results-empty="applicants"]').isVisible(), true);
    await dialog.locator('.results-dialog-close').click();
    assert.equal(await dialog.isVisible(), false, 'Closed preview cannot remain inline');
    await page.screenshot({path: path.join(output, 'programs-without-inline-box.png')});
    await open();
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(), false);
    await open();
    await dialog.getByRole('button', {name: 'Back to program', exact: true}).click();
    assert.equal(await dialog.isVisible(), false);
    assert.deepEqual(errors, []);
    const nojs = await browser.newContext({javaScriptEnabled: false});
    await nojs.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: base}]);
    const fallback = await nojs.newPage();
    await fallback.goto(base + process.env.QA_PREVIEW);
    assert.equal(await fallback.locator('#program-results-dialog').isVisible(), true, 'No-JavaScript direct review still works');
    await nojs.close();
    fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify({tabNavigation:true, closedHidden:true,
      compactWidths:[1600,768,390], close:true, escape:true, back:true, search:true, nojsFallback:true, errors}, null, 2));
    console.log('Tab navigation, hidden closed preview, compact desktop/mobile popup, close/Escape/back, search and no-JavaScript fallback passed. No publication submitted.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
