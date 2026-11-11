const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage(), errors = [], writes = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.method());
      if (request.url().includes(process.env.QA_PRINT_ROUTE)) requests.push(request.url());
    });
    const preview = page.locator('#membership-form-dialog');
    const print = page.locator('[data-membership-preview-print]');
    const ready = async () => {
      await page.waitForFunction(() => document.querySelector('#membership-form-dialog')?.open &&
        !document.querySelector('[data-membership-preview-print]').disabled);
      const frame = page.frames().find(item => item.url().includes('?preview=1'));
      assert(frame);
      assert(await frame.locator('.association-print-form').isVisible());
      assert.equal(await frame.locator('nav, button, .registration-controls').count(), 0);
      assert.match(await frame.locator('body').innerText(), /Approved member registration/);
      assert(await frame.locator('img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0)));
      return frame;
    };
    await page.goto(process.env.QA_URL + process.env.QA_MEMBER_ROUTE);
    await page.locator('[data-membership-form-preview]').click();
    let frame = await ready();
    assert.equal(page.url(), process.env.QA_URL + process.env.QA_MEMBER_ROUTE);
    assert.equal(context.pages().length, 1);
    await page.evaluate(() => { window.print = () => { window.parentPrintCalled = true; }; });
    await frame.evaluate(() => { window.print = () => { window.documentPrintCalled = true; }; });
    await print.click();
    assert(await frame.evaluate(() => window.documentPrintCalled));
    assert(!(await page.evaluate(() => window.parentPrintCalled)));
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      await page.waitForTimeout(250);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      assert(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const box = await print.boundingBox();
      assert(box.x >= 0 && box.x + box.width <= width && box.y >= 0);
      await page.screenshot({path: path.join(process.env.QA_OUTPUT, `member-popup-${width}.png`)});
    }
    // Escape must work even after focus moves inside the document.
    await frame.locator('.membership-form-title').click();
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('#membership-form-dialog').open);
    assert(await page.locator('[data-membership-form-preview]').evaluate(node => node === document.activeElement));
    const previousRequests = requests.length;
    await page.locator('[data-membership-form-preview]').click();
    await ready();
    assert(requests.length > previousRequests);
    await preview.getByRole('button', {name: 'Close form preview'}).click();
    assert(!await preview.evaluate(node => node.open));

    // The bookmarked print URL opens the same popup automatically, with no site navigation.
    await page.setViewportSize({width: 1440, height: 1000});
    const response = await page.goto(process.env.QA_URL + process.env.QA_PRINT_ROUTE);
    assert.match(response.headers()['cache-control'], /no-store/);
    frame = await ready();
    assert.equal(await page.locator('nav').count(), 0);
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'direct-popup.png')});
    await page.reload();
    await ready();
    await preview.getByRole('button', {name: 'Close form preview'}).click();
    await page.locator('[data-membership-preview-auto-open]').click();
    await ready();
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('#membership-form-dialog').open);

    // A failed/private response cannot become printable.
    await page.route('**/registration/print/?preview=1', route => route.fulfill({
      status: 403, contentType: 'text/html', body: '<p>Access denied</p>'}));
    await page.locator('[data-membership-preview-auto-open]').click();
    await page.waitForFunction(() => document.querySelector('[data-membership-preview-status]').textContent.includes('could not be loaded'));
    assert(await print.isDisabled());
    await preview.getByRole('button', {name: 'Close form preview'}).click();
    await page.unroute('**/registration/print/?preview=1');

    // Export the same document loaded by the print button using Chrome's print engine.
    const documentPage = await context.newPage();
    const documentResponse = await documentPage.goto(process.env.QA_URL + process.env.QA_PRINT_ROUTE + '?preview=1');
    assert.equal(documentResponse.headers()['x-frame-options'], 'SAMEORIGIN');
    assert.match(documentResponse.headers()['cache-control'], /no-store/);
    await documentPage.pdf({path: path.join(process.env.QA_OUTPUT, 'member-registration.pdf'),
      preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false});
    await documentPage.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    fs.writeFileSync(path.join(process.env.QA_OUTPUT, 'browser-results.json'), JSON.stringify({
      widths: [1440, 390, 320], direct_url_auto_opens: true, member_record_popup: true,
      print_document_only: true, ready_button: true, escape_and_focus: true,
      reopen_fetches_document: true, denied_document_keeps_print_disabled: true,
      private_same_origin_no_store: true, no_record_writes: true, javascript_errors: errors
    }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
