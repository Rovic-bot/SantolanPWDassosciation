const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT, errors = [];
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: base}]);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + process.env.QA_BUILDER);
    await page.locator('[data-save-draft]').click();
    await page.locator('[data-program-builder][data-saved="true"]').waitFor();
    assert.equal(await page.locator('[name=name]').inputValue(), '');
    await page.screenshot({path: path.join(output, 'incomplete-draft-desktop.png'), fullPage: true});
    await page.locator('[data-date][tabindex="0"]').click();
    await page.locator('[data-save-draft]').click();
    await page.waitForFunction(() => document.querySelector('[data-program-builder]').dataset.saved === 'true' &&
      document.querySelector('[name=registration_opens_at]').value !== '');
    assert.equal(await page.locator('[name=registration_closes_at]').inputValue(), '');
    await page.locator('[data-review-program]').click();
    await page.locator('[data-open-review]').click();
    await page.locator('#publish-program-form button').click();
    await page.getByText('Complete this field before publishing.', {exact: false}).first().waitFor();
    await page.goto(base + process.env.QA_EDIT);
    await page.locator('[name=name]').fill('Updated published program');
    await page.locator('textarea[name=description]').fill('Updated information for the published program.');
    await page.locator('[name=notes]').fill('Correct the public program details.');
    await page.locator('[data-save-draft]').click();
    await page.locator('[data-program-builder][data-saved="true"]').waitFor();
    await page.goto(base + process.env.QA_DETAIL);
    await page.getByRole('heading', {name: 'Updated published program', exact: true}).waitFor();
    await page.screenshot({path: path.join(output, 'published-details-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('.profile-status-controls summary').click();
    await page.locator('#program-status-form [name=notes]').fill('Unpublish and keep this program in the archive.');
    await page.locator('#program-status-form [name=confirm]').check();
    await page.screenshot({path: path.join(output, 'unpublish-mobile.png'), fullPage: true});
    await page.locator('#program-status-form button').click();
    await page.getByRole('heading', {name: 'Program archived', exact: true}).waitFor();
    await page.goto(base + process.env.QA_PORTFOLIO + '?status=archived');
    assert.equal(await page.locator('select[name=status] option[value=cancelled]').count(), 0);
    await page.getByRole('link', {name: 'Updated published program', exact: true}).waitFor();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'archived-program-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({passed: true, errors}, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
