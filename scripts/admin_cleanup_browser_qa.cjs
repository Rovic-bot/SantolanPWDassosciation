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
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: base}]);
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
      ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + process.env.QA_INBOX);
    assert.equal(await page.getByRole('link', {name: 'Association email settings', exact: true}).count(), 1);
    assert.equal(await page.locator('.referral-page-heading').count(), 0);
    await page.getByRole('link', {name: 'View ticket', exact: true}).click();
    const dialog = page.locator('#record-details-dialog');
    await page.waitForFunction(() => document.querySelector('[data-referral-reply] [name=version]')?.value === '1');
    assert.equal(new URL(page.url()).pathname, process.env.QA_INBOX);
    assert.match(await dialog.textContent(), /Synthetic concern for tests only/);
    for (const theme of ['light', 'dark']) {
      await page.evaluate(value => document.documentElement.dataset.dashboardTheme = value, theme);
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        assert.ok(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth + 1));
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        assert.deepEqual(await page.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(n => n.id);
          return ids.filter((id, i) => ids.indexOf(id) !== i);
        }), []);
        await page.screenshot({path: path.join(output, `ticket-${theme}-${width}.png`)});
      }
    }
    await page.setViewportSize({width: 1440, height: 1000});
    const form = dialog.locator('[data-referral-reply]');
    await form.locator('[name=member_message]').fill('Synthetic reply from the popup.');
    await form.locator('[name=notes]').fill('Synthetic private review note.');
    assert.equal(await form.locator('[data-gmail-compose], [data-gmail-confirm]').count(), 0);
    assert.match(await form.locator('[name=channel]').textContent(), /association@example.invalid/);
    assert.equal(await form.locator('[name=channel]').inputValue(), 'email');
    await form.locator('[name=channel]').selectOption('email');
    await form.locator('[data-reply-submit]').click();
    await page.waitForFunction(() => document.querySelector('[data-referral-reply] [name=version]')?.value === '2');
    assert.match(await dialog.textContent(), /Saved to development outbox/);
    await page.screenshot({path: path.join(output, 'ticket-reply-saved.png')});
    await page.keyboard.press('Escape');
    await page.waitForLoadState('networkidle');
    await page.getByRole('link', {name: 'View ticket', exact: true}).waitFor();
    assert.equal(await dialog.isVisible(), false);
    await page.goto(base + '/membership/applications/new/');
    await page.locator('[data-onsite-form]').waitFor();
    const lookup = await page.locator('.onsite-lookup').boundingBox();
    const status = await page.locator('.onsite-record-status').boundingBox();
    assert.ok(status.y >= lookup.y + lookup.height);
    assert.equal(await page.getByText('This document will be presented onsite', {exact: true}).count(), 0);
    await page.screenshot({path: path.join(output, 'onsite-status-position.png')});
    await page.goto(base + '/membership/registration/pdao/');
    assert.equal(await page.locator('[name=submission_token]').count(), 1);
    await page.goto(base + '/membership/reviews/pdao/');
    assert.doesNotMatch(await page.locator('main').textContent(), /This registration action is unavailable/);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({errors, checks:
      'Ticket popup; automatic review POST; reply composer; development email delivery; retained private notes; six responsive theme combinations; Escape; onsite status; saved PDAO form and staff queue'}, null, 2));
    console.log('PASS: ticket popup reply, six responsive themes, onsite layout and PDAO routes.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
