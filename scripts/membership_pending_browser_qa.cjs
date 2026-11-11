const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.QA_URL + process.env.QA_PUBLIC_ROUTE);
    await page.locator('[data-registration-privacy-open]').click();
    await page.locator('[data-registration-privacy-close]').click();
    assert.equal(await page.locator('[name=last_name]').getAttribute('placeholder'), 'e.g. Dela Cruz');
    assert.equal(await page.locator('[name=last_name]').inputValue(), '');
    const income = page.locator('[name=household_monthly_income]');
    assert.equal(await income.inputValue(), '1000');
    await income.click(); await income.hover(); await page.mouse.wheel(0, -100);
    await page.waitForFunction(() => document.querySelector('[name=household_monthly_income]').value === '1500', null, {timeout: 5000})
      .catch(async error => {
        await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'income-diagnostic.png')});
        throw new Error(`${error.message}; income=${await income.inputValue()}; focused=${await page.evaluate(() => document.activeElement?.outerHTML)}`);
      });
    await income.click(); await income.hover(); await page.mouse.wheel(0, -100);
    await page.waitForFunction(() => document.querySelector('[name=household_monthly_income]').value === '2000', null, {timeout: 5000})
      .catch(async error => { throw new Error(`${error.message}; income=${await income.inputValue()}; focused=${await income.evaluate(node => node === document.activeElement)}`); });
    await income.press('ArrowDown');
    assert.equal(await income.inputValue(), '1500');
    for (const value of ['735.50', '0']) {
      await income.fill(value);
      assert(await income.evaluate(node => node.checkValidity()));
    }
    await page.locator('[name=last_name]').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'online-placeholders.png')});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: process.env.QA_URL}]);
    await page.goto(process.env.QA_URL + process.env.QA_ROUTE);
    await page.evaluate(() => { localStorage.setItem('santolan-dashboard-theme', 'dark'); });
    await page.reload();
    // Leaving pending must work independently of incomplete edits in the approval form.
    await page.locator('#association-review-form [name=first_name]').fill('');
    await page.locator('[data-pending-open]').click();
    const dialog = page.locator('#membership-pending-dialog');
    assert(await dialog.evaluate(node => node.open));
    assert((await dialog.innerText()).includes(process.env.QA_RECIPIENT));
    await dialog.getByRole('button', {name: 'Cancel', exact: true}).click();
    assert(!await dialog.evaluate(node => node.open));
    await page.locator('[data-pending-open]').click();
    await dialog.locator('textarea').fill('Please bring a clear copy of your PWD ID.\nVisit the Help Desk for assistance.');
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1000});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path: path.join(process.env.QA_OUTPUT, `pending-message-${width}.png`)});
    }
    await dialog.getByRole('button', {name: 'Send email and keep pending'}).click();
    await page.locator('#pending-email-history').getByText('Saved to test outbox', {exact: false}).waitFor();
    assert.match(await page.locator('.onsite-record-status').innerText(), /Pending review/);
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('[data-membership-form-preview]').click();
    const preview = page.locator('#membership-form-dialog');
    const print = preview.locator('[data-membership-preview-print]');
    await page.waitForFunction(() => !document.querySelector('[data-membership-preview-print]').disabled);
    assert.equal(page.url(), process.env.QA_URL + process.env.QA_ROUTE);
    const frame = page.frames().find(item => item.url().includes('?preview=1'));
    assert(frame);
    assert(await frame.locator('.association-print-form').isVisible());
    await frame.evaluate(() => { window.print = () => { window.previewPrintCalled = true; }; });
    await print.click();
    assert(await frame.evaluate(() => window.previewPrintCalled));
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1000});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path: path.join(process.env.QA_OUTPUT, `submitted-form-preview-${width}.png`)});
    }
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('#membership-form-dialog').open);
    assert(!await preview.evaluate(node => node.open));
    await page.waitForFunction(() => document.querySelector('[data-membership-form-preview]') === document.activeElement);
    assert(await page.locator('[data-membership-form-preview]').evaluate(node => node === document.activeElement));
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
