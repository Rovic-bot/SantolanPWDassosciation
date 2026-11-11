/* Read-only acceptance against the retained main development instance. */
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const local = path.join(root, '.local/ewaf-twelve-demo');
const manifest = JSON.parse(fs.readFileSync(path.join(local, 'connection.json'), 'utf8'));
const fixtures = JSON.parse(fs.readFileSync(path.join(local, 'seed-summary.json'), 'utf8'));
assert.equal(manifest.purpose, 'EWAF_TWELVE_PERSISTENT_DEMO');
const origin = `http://127.0.0.1:${manifest.http_port}`;
const output = path.join(root, 'docs/results-popup-2026-10-27');
fs.mkdirSync(output, {recursive: true});
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const health = await context.request.get(origin + '/ewaf-demo/health/');
    assert.equal((await health.json()).instance_id, manifest.instance_id);
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(manifest.admin_username);
    await page.locator('[name=password]').fill(manifest.admin_password);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    await page.goto(origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
    await page.locator('#weight-SES').waitFor();
    assert.equal(await page.locator('#scoring-policy').count(), 0);
    for (const text of ['Calculation rules and member information', 'Drag the criterion sliders like volume controls',
      'Calculation uses dataset min', 'Review policy version', 'SES = income need']) {
      assert(!(await page.locator('main').innerText()).includes(text));
    }
    await page.screenshot({path: path.join(output, 'current-vault.png'), fullPage: true});
    for (const scenario of fixtures.scenarios) {
      await page.goto(`${origin}/ewaf/programs/${scenario.program_id}/`, {waitUntil: 'networkidle'});
      assert.equal(await page.locator('#results table tbody tr').count(), 12);
      assert(await page.getByRole('button', {name: 'SELECT FOR ASSISTANCE', exact: true}).count());
      assert.equal(await page.getByText('Record beneficiary decision', {exact: true}).count(), 0);
    }
    await page.locator('#results').screenshot({path: path.join(output, 'current-ranking.png')});
    await page.goto(origin + '/announcements/manage/results/', {waitUntil: 'networkidle'});
    assert(await page.locator('.program-grid .program-card').count());
    assert.equal(await page.locator('select[name=program]').count(), 0);
    await page.screenshot({path: path.join(output, 'current-program-grid.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'current-program-grid-mobile.png'), fullPage: true});
    await page.setViewportSize({width: 1440, height: 1100});
    const affected = page.locator('.program-grid .program-card').filter({hasText: 'HM Focus'});
    const review = affected.getByRole('link', {name: 'Review and publish'});
    const reviewURL = new URL(await review.getAttribute('href'), origin).href;
    await review.click();
    await page.locator('#program-results-dialog[open]').waitFor();
    assert.equal(page.url(), `${origin}/announcements/manage/results/`);
    assert.equal(await page.locator('#generate-results-form').getAttribute('action'), new URL(reviewURL).pathname);
    assert(await page.locator('#results-dialog-title').evaluate(element => element === document.activeElement));
    // Tab and Shift+Tab stay inside the modal; Escape returns to the card.
    for (const key of ['Shift+Tab', 'Tab', 'Tab', 'Tab', 'Tab', 'Tab', 'Tab']) {
      await page.keyboard.press(key);
      assert(await page.evaluate(() => document.querySelector('#program-results-dialog').contains(document.activeElement)));
    }
    await page.keyboard.press('Escape');
    await page.locator('#program-results-dialog').waitFor({state: 'detached'});
    assert(await review.evaluate(element => element === document.activeElement));
    await review.click();
    await page.locator('#program-results-dialog[open]').waitFor();
    assert.equal(await page.locator('[aria-label="Program applicants"] tbody tr').count(), 12);
    assert.equal(await page.locator('[aria-label="Selected program members"] tbody tr').count(), 1);
    const body = await page.locator('#program-results').innerText();
    assert(!body.includes('APPLICATION_NOT_CANDIDATE'));
    assert(!body.includes('APPLICATION_REVIEW_UNRESOLVED'));
    assert(!body.includes('Ben Testbravo'));
    const reference = (await page.locator('[aria-label="Selected program members"] tbody tr td').nth(1).innerText()).trim();
    assert(reference.startsWith('SPWDA-'));
    assert((await page.locator('[aria-label="Program applicants"]').innerText()).includes(reference));
    assert(await page.getByRole('button', {name: 'Publish results', exact: true}).isEnabled());
    const left = await page.locator('section[aria-label="Members who applied"]').boundingBox();
    const right = await page.locator('section[aria-label="Selected members"]').boundingBox();
    assert(right.x > left.x && Math.abs(right.y - left.y) < 2);
    await page.screenshot({path: path.join(output, 'affected-program-desktop.png')});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    const mobileLeft = await page.locator('section[aria-label="Members who applied"]').boundingBox();
    const mobileRight = await page.locator('section[aria-label="Selected members"]').boundingBox();
    assert(mobileRight.y > mobileLeft.y && Math.abs(mobileRight.x - mobileLeft.x) < 2);
    const publish = await page.getByRole('button', {name: 'Publish results', exact: true}).boundingBox();
    assert(publish.y >= 0 && publish.y + publish.height <= 1000);
    await page.screenshot({path: path.join(output, 'affected-program-mobile.png')});
    await page.getByRole('button', {name: 'Close', exact: true}).click();
    await page.locator('#program-results-dialog').waitFor({state: 'detached'});
    assert(await review.evaluate(element => element === document.activeElement));
    // A direct program URL also opens its popup rather than a separate results page.
    await page.goto(reviewURL, {waitUntil: 'networkidle'});
    await page.locator('#program-results-dialog[open]').waitFor();
    assert.equal(await page.locator('[aria-label="Program applicants"] tbody tr').count(), 12);
    await page.getByRole('button', {name: 'Close results preview'}).click();
    await page.locator('#program-results-dialog').waitFor({state: 'detached'});
    assert(await page.locator('.program-grid').isVisible());
    assert.deepEqual(errors, []);
    console.log('PASS: retained main instance; program grid; popup without navigation; keyboard focus containment and return; Escape/Close/X; direct links; affected HM program has 12 applicants, 1 selected and enabled Publish results; no raw review codes; full references; desktop columns/mobile stacking. No decisions, rankings or publications changed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
