const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.QA_URL + process.env.QA_ONSITE);
    await page.locator('[data-review-application]:visible').waitFor();
    assert.equal(await page.locator('[data-save-draft], [data-restore-draft], [data-draft-note]').count(), 0);
    for (const name of ['email', 'pwd_number']) {
      assert.equal(await page.locator(`[data-onsite-form] [name="${name}"]`).evaluate(field => field.required), true);
    }
    for (const [name, value] of Object.entries(JSON.parse(process.env.QA_FORM_DATA))) {
      const field = page.locator(`[data-onsite-form] [name="${name}"]`);
      if (await field.getAttribute('type') === 'checkbox') await field.check();
      else if (await field.evaluate(node => node.tagName) === 'SELECT') await field.selectOption(value);
      else await field.fill(String(value));
    }
    const email = page.locator('[data-onsite-form] [name=email]');
    await email.fill('');
    await page.getByRole('button', {name: 'Review application', exact: false}).click();
    assert.equal(await page.locator('[data-onsite-review-dialog][open]').count(), 0);
    assert.equal(await email.evaluate(field => field.validity.valueMissing), true);
    await email.fill('invalid');
    assert.equal(await email.evaluate(field => field.validity.typeMismatch), true);
    await email.fill('onsite@example.invalid');
    await page.getByRole('button', {name: 'Review application', exact: false}).click();
    await page.locator('[data-onsite-review-dialog][open]').waitFor();
    assert.match(await page.locator('[data-review-content]').innerText(), /Fictional/);
    if (process.env.QA_ONSITE_ONLY === '1') {
      assert.match(await page.locator('[data-review-content]').innerText(), /onsite@example.invalid/);
      assert.deepEqual(errors, []);
      console.log('Required onsite email/PWD, missing/invalid email blocking, and valid review passed.');
      return;
    }
    await page.getByRole('button', {name: 'Continue editing', exact: true}).click();
    await page.getByLabel('Reference number', {exact: true}).fill(process.env.QA_REFERENCE);
    await page.getByRole('button', {name: 'Load online application', exact: true}).click();
    await page.waitForURL(process.env.QA_URL + process.env.QA_MEMBER);
    assert.equal(await page.locator('dialog[open]').count(), 0);
    await page.waitForFunction(() => {
      const photo = document.querySelector('.member-record-portrait');
      return photo?.complete && photo.naturalWidth > 0;
    });
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'member-photo-desktop.png')});
    await page.getByRole('link', {name: 'Edit profile', exact: false}).click();
    await page.locator('.member-editor').waitFor();
    for (const name of JSON.parse(process.env.QA_FIELDS)) {
      assert.equal(await page.locator(`.member-editor [name="${name}"]`).count(), 1, name);
    }
    assert.equal(await page.locator('.member-editor [name=first_name]').inputValue(), 'Fictional');
    // The current member editor includes the existing supporting-documents section.
    assert.equal(await page.locator('.member-editor [data-onsite-section]').count(), 7);
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `edit overflow ${width}`);
      if (width !== 320) await page.screenshot({path: path.join(process.env.QA_OUTPUT, `edit-${width}.png`)});
    }
    await page.locator('[name=guardian_name]').fill('Updated fictional guardian');
    await page.locator('[name=notes]').fill('Synthetic browser profile correction.');
    await page.getByRole('button', {name: 'Update member record', exact: true}).click();
    await page.waitForURL(process.env.QA_URL + process.env.QA_MEMBER);
    await page.waitForFunction(() => document.querySelector('.member-record-portrait')?.naturalWidth > 0);
    await page.goto(process.env.QA_URL + process.env.QA_PLAIN_MEMBER);
    assert.equal(await page.locator('.member-record-avatar').innerText(), 'FP');
    assert.equal(await page.locator('.member-record-portrait').count(), 0);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'member-initials-320.png')});
    assert.deepEqual(errors, []);
    console.log('Onsite review without drafts, full-page reference lookup, loaded private photo, initials fallback, matching edit fields, mobile layout and saved profile correction passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
