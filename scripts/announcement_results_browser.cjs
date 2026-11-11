/* Read-only acceptance against the identity-verified local development instance. */
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, '.local/ewaf-twelve-demo/connection.json'), 'utf8'));
assert.equal(manifest.purpose, 'EWAF_TWELVE_PERSISTENT_DEMO');
const origin = process.env.QA_URL || `http://127.0.0.1:${manifest.http_port}`;
assert(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname));
const output = path.join(root, 'docs/admin-recorded-results-2026-10-28');
fs.mkdirSync(output, {recursive: true});
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    assert.equal((await (await context.request.get(origin + '/ewaf-demo/health/')).json()).instance_id, manifest.instance_id);
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(manifest.admin_username);
    await page.locator('[name=password]').fill(manifest.admin_password);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    // All application requests after login must be read-only.
    await context.route('**/*', route => {
      const request = route.request();
      if (!['GET', 'HEAD'].includes(request.method())) {
        errors.push('Unexpected mutation: ' + request.method());
        return route.abort();
      }
      return new URL(request.url()).origin === origin ? route.continue() : route.abort();
    });
    await page.goto(origin + '/announcements/manage/', {waitUntil: 'networkidle'});
    assert.equal(await page.getByRole('heading', {name: 'Announcements', exact: true}).count(), 1);
    assert.equal(await page.getByRole('heading', {name: 'Prepare and publish program results', exact: true}).count(), 1);
    assert.equal(await page.getByText('Association updates', {exact: true}).count(), 0);
    assert.equal(await page.getByRole('link', {name: 'Saved announcements', exact: true}).count(), 0);
    const count = await page.locator('.program-grid .program-card').count();
    assert(count > 0);
    const labels = await page.locator('[data-result-status]').allTextContents();
    assert(labels.every(label => label.trim().startsWith('Results ')));
    const hm = page.locator('.program-card').filter({hasText: 'HM Focus'});
    assert.equal((await hm.locator('[data-result-status]').innerText()).trim(), 'Results draft');
    assert.equal(await hm.getByRole('link', {name: 'View public results'}).count(), 0);
    await page.screenshot({path: path.join(output, 'announcements-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'announcements-mobile.png'), fullPage: true});
    await page.setViewportSize({width: 1440, height: 1100});
    await page.getByRole('searchbox', {name: 'Search programs by title or code'}).fill('HM Focus');
    await page.getByRole('button', {name: 'Apply filters'}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('.program-grid .program-card').count(), 1);
    const review = page.getByRole('link', {name: 'Review and publish'});
    const programPath = new URL(await review.getAttribute('href'), origin).pathname;
    const gridURL = page.url();
    await review.click();
    await page.locator('#program-results-dialog[open]').waitFor();
    assert.equal(page.url(), gridURL);
    const canPublish = await page.getByRole('button', {name: 'Publish results', exact: true}).isEnabled();
    assert(canPublish, 'Recorded results must be publishable despite earlier-ranking review blockers.');
    assert.equal(await page.locator('#generate-results-form').getAttribute('action'), programPath);
    assert.equal(await page.getByRole('button', {name: 'Publish results', exact: true}).getAttribute('value'), 'PUBLISH_RECORDED_RESULTS');
    const names = await page.locator('#program-results tbody td:first-child').allTextContents();
    assert(names.some(name => name.includes('Ben Testbravo')));
    assert(names.every(name => !name.includes('***')));
    const reviewMessages = await page.locator('#program-results-dialog .alert').allTextContents();
    assert(await page.locator('#results-dialog-title').evaluate(element => element === document.activeElement));
    for (const key of ['Shift+Tab', 'Tab', 'Tab', 'Tab', 'Tab']) {
      await page.keyboard.press(key);
      assert(await page.evaluate(() => document.querySelector('#program-results-dialog').contains(document.activeElement)));
    }
    await page.screenshot({path: path.join(output, 'review-dialog.png')});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'review-dialog-mobile.png')});
    await page.setViewportSize({width: 1440, height: 1100});
    await page.keyboard.press('Escape');
    await page.locator('#program-results-dialog').waitFor({state: 'detached'});
    assert(await review.evaluate(element => element === document.activeElement));
    await page.goto(origin + '/announcements/manage/results/', {waitUntil: 'networkidle'});
    assert.deepEqual(await page.locator('[data-result-status]').allTextContents(), labels);
    const publicPage = await browser.newPage({viewport: {width: 1440, height: 1000}});
    await publicPage.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await publicPage.goto(origin + '/results/', {waitUntil: 'networkidle'});
    assert.equal(await publicPage.getByText('No published results yet', {exact: true}).count(), 1);
    await publicPage.screenshot({path: path.join(output, 'public-results.png'), fullPage: true});
    assert.deepEqual(errors, []);
    const result = {cards: count, labels: labels.map(label => label.trim()),
      desktop: 'passed', mobile: 'passed', search: 'passed', dialog: 'passed',
      keyboard: 'passed', saved_announcements_removed: 'passed', admin_full_names: 'passed', public_visibility: 'passed',
      publish_enabled: canPublish, review_messages: reviewMessages.map(message => message.trim()),
      business_mutations: 0, javascript_errors: errors};
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
