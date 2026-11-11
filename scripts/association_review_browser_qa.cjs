const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const routes = JSON.parse(process.env.QA_ROUTES);
const fields = JSON.parse(process.env.QA_FIELDS);

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1100}});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.QA_URL + routes.pending);
    await page.locator('.association-review').waitFor();
    const form = page.locator('#association-review-form');
    for (const name of fields) assert(await form.locator(`[name="${name}"]`).count(), `Missing review field: ${name}`);
    const sectionCount = await form.locator('.onsite-section[id^=review-section]').count();
    for (const name of ['version', 'csrfmiddlewaretoken', 'prpwd_lookup_number', 'acknowledgement']) {
      assert.equal(await form.locator(`input[type=hidden][name="${name}"]`).count(), 1);
    }
    assert.equal(await page.locator('[data-onsite-form]').count(), 0, 'Review must not create a new onsite registration');
    assert.equal(await form.locator('[value=decline_registration]').getAttribute('formnovalidate'), '');
    assert(await page.getByRole('heading', {name: 'Supporting documents', exact: true}).isVisible());
    for (const theme of ['dark', 'light']) {
      await page.evaluate(value => {localStorage.setItem('santolan-dashboard-theme', value); document.documentElement.dataset.dashboardTheme = value;}, theme);
      for (const width of [1600, 1024, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1100});
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Overflow: ${theme} ${width}`);
        if ([1600, 390].includes(width)) await page.screenshot({path: path.join(process.env.QA_OUTPUT, `review-${theme}-${width}.png`)});
      }
    }
    await page.setViewportSize({width: 1600, height: 1100});
    const approve = form.locator('[value=approve_registration]');
    assert(await approve.isDisabled(), 'PRPWD remains required');
    await context.route('https://registry.example.test/**', route => route.fulfill({body: 'Synthetic registry'}));
    const popupPromise = page.waitForEvent('popup');
    await page.locator('[data-prpwd-open]').click();
    const popup = await popupPromise;
    await popup.close();
    assert(await approve.isEnabled(), 'Manual registry opening retained');
    await form.locator('[name=pwd_number]').fill('00-0000-000-0000009');
    assert(await approve.isDisabled(), 'Changing the PWD number requires a fresh check');
    await page.locator('.association-review-history > summary').click();
    await page.locator('.association-review-history-body > details > summary').first().click();
    assert(await page.locator('.association-review-history-body').getByText('Fictional', {exact: true}).first().isVisible());
    for (const state of ['approved', 'declined']) {
      await page.goto(process.env.QA_URL + routes[state]);
      assert.equal(await page.locator('#association-review-form').count(), 0);
      assert.equal(await page.locator('.association-review-readonly :is(input, select, textarea):not(:disabled)').count(), 0);
      assert.equal((await page.locator('.onsite-record-status strong').innerText()).toLowerCase(), state);
      assert(await page.locator('.association-review-values').getByText(state === 'approved' ? 'Approved' : 'Declined', {exact: true}).isVisible());
    }
    const viewer = await browser.newContext();
    await viewer.addCookies([{name: 'sessionid', value: process.env.QA_VIEWER_SESSION, url: process.env.QA_URL}]);
    const view = await viewer.newPage();
    await view.goto(process.env.QA_URL + routes.pending);
    assert.equal(await view.locator('#association-review-form, [data-prpwd-review]').count(), 0);
    assert.equal(await view.getByRole('heading', {name: 'Supporting documents', exact: true}).count(), 0);
    assert.equal(await view.locator('.association-review-readonly :is(input, select, textarea):not(:disabled)').count(), 0);
    const noJS = await browser.newContext({javaScriptEnabled: false});
    await noJS.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL}]);
    const fallback = await noJS.newPage();
    await fallback.goto(process.env.QA_URL + routes.pending);
    assert.equal(await fallback.locator('#association-review-form .onsite-section[id^=review-section]').count(), sectionCount);
    for (const name of fields) assert(await fallback.locator(`#association-review-form [name="${name}"]`).count(), `Missing no-JS field: ${name}`);
    await page.route('**/synthetic-review-errors/', route => route.fulfill({contentType: 'text/html', body: fs.readFileSync(path.join(process.env.QA_OUTPUT, 'invalid.html'))}));
    await page.goto(process.env.QA_URL + '/synthetic-review-errors/');
    await page.locator('#registration-errors').waitFor();
    await page.setViewportSize({width: 390, height: 1100});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'review-validation-390.png')});
    assert.deepEqual(errors, []);
    console.log('All editable fields and hidden controls, PRPWD gating/reset, protected documents, original history, approved/declined/view-only states, no-JS form, errors, and light/dark layouts at five widths passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
