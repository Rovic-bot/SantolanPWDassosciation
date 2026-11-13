const assert = require('node:assert/strict'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const origin = process.env.QA_URL, output = process.env.QA_OUTPUT;
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: origin}]);
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + process.env.QA_RECORD);
    assert.equal(await page.getByRole('link', {name: 'Start Association Membership', exact: true}).count(), 0);
    const claim = page.locator('form[action$="/claim/"]');
    await claim.locator('[name=pwd_number]').fill('00-0000-000-0000123');
    await claim.locator('[name=confirmed]').check();
    await claim.getByRole('button', {name: 'Record ID as claimed', exact: true}).click();
    await page.getByRole('link', {name: 'Start Association Membership', exact: true}).waitFor();
    await page.screenshot({path: path.join(output, 'claimed-id-desktop.png'), fullPage: true});
    await page.getByRole('link', {name: 'Start Association Membership', exact: true}).click();
    await page.getByRole('heading', {name: 'Association membership from PDAO', exact: true}).waitFor();
    assert.equal(await page.locator('[name=first_name]').inputValue(), 'Fictional');
    assert.equal(await page.locator('[name=suffix]').inputValue(), 'Jr.');
    assert.equal(await page.locator('[name=birthdate]').inputValue(), '1990-01-02');
    assert.equal(await page.locator('[name=pwd_number]').inputValue(), '00-0000-000-0000123');
    assert.equal(await page.locator('[name=disability_type]').inputValue(), 'Physical / Orthopedic');
    assert.ok(await page.locator('[name=first_name]').isDisabled());
    assert.equal(await page.locator('[name=four_ps_member]').inputValue(), '');
    assert.equal(await page.locator('[name=four_ps_member]').evaluate(input => input.required), true);
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1000});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Membership form must fit viewport');
      await page.screenshot({path: path.join(output, 'prefilled-' + width + '.png'), fullPage: true});
    }
    await page.locator('[name=four_ps_member]').selectOption('No');
    await page.locator('[name=household_monthly_income]').fill('5000');
    await page.locator('[name=household_members]').fill('3');
    await page.locator('[name=acknowledgement]').check();
    await page.locator('[name=membership_requested]').check();
    await page.locator('[data-review-application]').click();
    const dialog = page.locator('[data-onsite-review-dialog]');
    await dialog.waitFor({state: 'visible'});
    const summary = await dialog.innerText();
    assert.ok(summary.includes('Fictional'));
    assert.ok(summary.includes('Physical / Orthopedic'));
    assert.ok(summary.includes('00-0000-000-0000123'));
    await page.screenshot({path: path.join(output, 'review-mobile.png')});
    await dialog.locator('[data-confirm-registration]').click();
    await page.waitForURL(/\/membership\/registrations\/AMR-/);
    await page.getByText('Association membership review', {exact: true}).waitFor();
    await page.screenshot({path: path.join(output, 'saved-membership.png'), fullPage: true});
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
