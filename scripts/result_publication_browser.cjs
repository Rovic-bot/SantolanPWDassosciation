/* Disposable-only journey including a selected applicant with confirmed delivery. */
const path = require('path'), fs = require('fs'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  assert(process.env.G12_ARTIFACT_DIR, 'Use the verified disposable MySQL test runner.');
  const origin = new URL(process.env.QA_URL).origin;
  assert(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname));
  const output = path.join(process.env.G12_ARTIFACT_DIR, 'result-publication');
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(process.env.QA_USERNAME);
    await page.locator('[name=password]').fill(process.env.QA_PASSWORD);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    const program = process.env.QA_PROGRAM;
    await page.goto(`${origin}/ewaf/programs/${program}/`, {waitUntil: 'networkidle'});
    const second = page.locator(`.ewaf-ranking-table tr[data-applicant="${process.env.QA_SECOND}"]`);
    await second.locator('[data-applicant-open]').click();
    await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' &&
        new URL(response.url()).pathname === `/ewaf/programs/${program}/`),
      page.locator('#readiness').getByRole('button', {name: 'Select for assistance', exact: true}).click(),
    ]);
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(() => !document.querySelector('#readiness')?.hasAttribute('aria-busy'));
    assert((await second.innerText()).includes('Selected for assistance'),
      JSON.stringify({row: await second.innerText(), panel: await page.locator('#readiness').innerText()}));
    await page.goto(`${origin}/announcements/manage/results/`, {waitUntil: 'networkidle'});
    assert(await page.locator('[data-announcement-select]').count());
    await page.locator(`[data-announcement-select="${program}"]`).click();
    await page.screenshot({path: path.join(output, 'program-grid.png'), fullPage: true});
    const review = page.locator(`[data-announcement-panel="${program}"] [data-results-preview]`);
    await review.click();
    await page.locator('#program-results-dialog[open]').waitFor();
    await page.locator('#results-applicant-table [data-results-applicant]').first().waitFor({state: 'visible'});
    assert.equal(new URL(page.url()).origin + new URL(page.url()).pathname, `${origin}/announcements/manage/results/`);
    assert.equal(new URL(page.url()).searchParams.get('selected'), program);
    assert.equal(new URL(await page.locator('#generate-results-form').getAttribute('action'), origin).href, `${origin}/announcements/manage/results/${program}/`);
    assert(await page.locator('#results-dialog-title').evaluate(element => element === document.activeElement));
    await page.keyboard.press('Tab');
    assert(await page.evaluate(() => document.querySelector('#program-results-dialog').contains(document.activeElement)));
    await page.keyboard.press('Escape');
    await page.locator('#program-results-dialog[open]').waitFor({state: 'hidden'});
    assert(await review.evaluate(element => element === document.activeElement));
    await review.click();
    await page.locator('#program-results-dialog[open]').waitFor();
    await page.locator('#results-applicant-table [data-results-applicant]').first().waitFor({state: 'visible'});
    assert.equal(await page.locator('#results-applicant-table [data-results-applicant]').count(), 12);
    assert.equal(await page.locator('#results-selection-table [data-results-selection]').count(), 2);
    assert(!(await page.locator('#program-results').innerText()).includes('APPLICATION_'));
    assert((await page.locator('#results-selection-table').innerText()).includes(process.env.QA_REFERENCE));
    assert((await page.locator('#results-selection-table').innerText()).includes('Ben Testbravo'));
    assert(!(await page.locator('#program-results').innerText()).includes('***'));
    assert(await page.getByRole('button', {name: 'Publish results', exact: true}).isEnabled());
    const left = await page.locator('section[aria-labelledby="results-applicants-title"]').boundingBox();
    const right = await page.locator('section[aria-labelledby="results-selections-title"]').boundingBox();
    assert(right.x > left.x && Math.abs(right.y - left.y) < 2);
    await page.screenshot({path: path.join(output, 'preview-desktop.png')});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    const mobileLeft = await page.locator('section[aria-labelledby="results-applicants-title"]').boundingBox();
    const mobileRight = await page.locator('section[aria-labelledby="results-selections-title"]').boundingBox();
    assert(mobileRight.y > mobileLeft.y && Math.abs(mobileRight.x - mobileLeft.x) < 2);
    await page.getByRole('button', {name: 'Publish results', exact: true}).scrollIntoViewIfNeeded();
    const publish = await page.getByRole('button', {name: 'Publish results', exact: true}).boundingBox();
    assert(publish.y >= 0 && publish.y + publish.height <= 1000);
    await page.screenshot({path: path.join(output, 'preview-mobile.png')});
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('#program-results-dialog [name="selection_reason"]').fill('Synthetic reviewed selection after current ranking and confirmed receipt.');
    await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' &&
        new URL(response.url()).pathname === `/announcements/manage/results/${program}/`, {timeout: 120000}),
      page.getByRole('button', {name: 'Publish results', exact: true}).click(),
    ]);
    await page.waitForFunction(() => !document.querySelector('#program-results-dialog')?.hasAttribute('aria-busy'));
    assert((await page.locator('#program-results-dialog').innerText()).includes('Program results published.'));
    await page.getByRole('button', {name: 'Close results preview', exact: true}).click();
    await page.locator(`[data-announcement-panel="${program}"]`).getByRole('link', {name: /View public results/}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('[data-result-applicant]').count(), 12);
    assert.equal(await page.locator('[data-result-recipient]').count(), 2);
    assert(!(await page.locator('main').innerText()).includes('Ben Testbravo'));
    assert((await page.locator('[aria-label="Published recipient records"]').innerText()).includes(process.env.QA_REFERENCE));
    await page.screenshot({path: path.join(output, 'published-results.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('PASS browser: completed selected applicant retained; additional selection; program grid; popup without navigation; Escape/focus return; 12 applicants and 2 selected; Publish results via correct program form; full names in Admin and masked public names; desktop columns/mobile stacking.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
