/* Synthetic disposable-server journey: edit -> AHP -> approve -> rank -> explain. */
const path = require('path');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const origin = new URL(process.env.QA_URL).origin;
  assert(['localhost', '127.0.0.1'].includes(new URL(origin).hostname));
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin
      ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(process.env.QA_USERNAME);
    await page.locator('[name=password]').fill(process.env.QA_PASSWORD);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/ewaf/vault/');
    assert.equal(await page.locator('#scoring-policy').count(), 0);
    assert(!(await page.locator('main').innerText()).includes('Drag the criterion sliders like volume controls'));
    await page.locator('#weight-SES').waitFor();
    await page.locator('#weight-SES').evaluate(input => {
      input.value = '62.5'; input.dispatchEvent(new Event('input', {bubbles: true}));
    });
    await page.locator('#preview-weights').click();
    await page.waitForFunction(() => {
      const form = document.querySelector('#ewaf-configuration-form');
      return form.elements.weight_review.value && !form.querySelector('button[value=LOCKED]').disabled;
    });
    const proposal = JSON.parse(await page.locator('[name=slider_proposal]').inputValue());
    assert.equal(proposal.weights.SES, 6250);
    for (const code of ['ES', 'PA', 'HM']) assert.equal(proposal.weights[code], 1250);
    await page.locator('[name=reason]').fill('SYNTHETIC browser approval shared by two existing programs.');
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'shared-weights-preview.png'), fullPage: true});
    await page.locator('button[value=LOCKED]').click();
    await page.waitForLoadState('networkidle');
    assert((await page.locator('main').innerText()).includes('Configuration approved for programs without published results.'));
    assert((await page.locator('main').innerText()).includes('Programs with published results keep their ranking weights'));
    for (const [index, program] of JSON.parse(process.env.QA_PROGRAMS).entries()) {
      await page.goto(origin + '/ewaf/', {waitUntil: 'networkidle'});
      await page.locator(`[data-select-program="${program}"]`).click();
      await page.locator(`[data-program-panel="${program}"]`)
        .getByRole('link', {name: 'Open full ranking', exact: true}).click();
      await page.waitForLoadState('networkidle');
      assert.equal(await page.locator('#configuration').count(), 0);
      assert(await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).isEnabled());
      assert.equal(await page.locator('#id_generate_reason').count(), 0);
      await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).click();
      await page.waitForLoadState('networkidle');
      const rows = page.locator('#results table tbody tr');
      assert.equal(await rows.count(), 12);
      assert.equal((await rows.first().locator('th a').innerText()).trim(), 'Ana Testalpha');
      await page.locator('#results').screenshot({path: path.join(process.env.QA_OUTPUT, `shared-weights-program-${index + 1}.png`)});
      await rows.first().locator('.ewaf-score-link').click();
      await page.waitForLoadState('networkidle');
      assert(new URL(page.url()).pathname.endsWith('/breakdown/'));
      assert(new URL(page.url()).searchParams.has('applicant'));
      const explanation = await page.locator('main').innerText();
      assert(explanation.includes('Ana Testalpha'));
      assert(explanation.includes('62.50%'));
      assert(explanation.includes('12.50%'));
      await page.screenshot({path: path.join(process.env.QA_OUTPUT, `shared-weights-scoring-${index + 1}.png`), fullPage: true});
    }
    const fs = require('fs');
    const output = path.join(process.env.QA_OUTPUT, 'selection-results');
    fs.mkdirSync(output, {recursive: true});
    const program = JSON.parse(process.env.QA_PROGRAMS)[0];
    await page.goto(`${origin}/ewaf/programs/${program}/`, {waitUntil: 'networkidle'});
    const ranked = page.locator('#results table tbody tr');
    assert.equal(await ranked.locator('[data-applicant-open]').count(), 12);
    await ranked.first().locator('[data-applicant-open]').click();
    const selectedReference = (await page.locator('#readiness .ewaf-input-card-header p').innerText()).trim();
    await page.locator('#readiness').getByRole('button', {name: 'Select for assistance', exact: true}).click();
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(() => document.querySelector('#results table tbody tr')
      ?.textContent.includes('Selected for assistance'));
    assert((await ranked.first().innerText()).includes('Selected for assistance'));
    await page.locator('#results').screenshot({path: path.join(output, 'ranking-selection.png')});
    await page.goto(`${origin}/announcements/manage/results/`, {waitUntil: 'networkidle'});
    assert(await page.locator('[data-announcement-select]').count());
    await page.screenshot({path: path.join(output, 'program-grid.png'), fullPage: true});
    await page.locator(`[data-announcement-select="${program}"]`).click();
    await page.locator(`[data-announcement-panel="${program}"] [data-results-preview]`).click();
    await page.locator('#program-results-dialog[open]').waitFor();
    await page.locator('#results-applicant-table [data-results-applicant]').first().waitFor({state: 'visible'});
    assert.equal(await page.locator('#results-applicant-table [data-results-applicant]').count(), 12);
    assert.equal(await page.locator('#results-selection-table [data-results-selection]').count(), 1);
    const left = await page.locator('section[aria-labelledby="results-applicants-title"]').boundingBox();
    const right = await page.locator('section[aria-labelledby="results-selections-title"]').boundingBox();
    assert(right.x > left.x && Math.abs(left.y - right.y) < 2);
    await page.screenshot({path: path.join(output, 'publication-preview.png'), fullPage: true});
    await page.locator('#program-results-dialog [name="selection_reason"]')
      .fill('SYNTHETIC authorized selection after reviewing the current ranking and available slots.');
    const [publicationResponse] = await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' &&
        new URL(response.url()).pathname === `/announcements/manage/results/${program}/`, {timeout: 120000}),
      page.getByRole('button', {name: 'Publish results', exact: true}).click(),
    ]);
    assert(publicationResponse.status() < 400, 'Publication POST must succeed or redirect.');
    await page.waitForFunction(() => !document.querySelector('#program-results-dialog')?.hasAttribute('aria-busy'));
    const publicationFeedback = await page.locator('#program-results-dialog .alert, #program-results-dialog .errorlist, #program-results-dialog [data-results-message]').allTextContents();
    assert(publicationFeedback.some(message => message.includes('Program results published.')),
      `Publication must be confirmed: ${JSON.stringify(publicationFeedback)}`);
    await page.getByRole('button', {name: 'Close results preview', exact: true}).click();
    await page.locator(`[data-announcement-panel="${program}"]`)
      .getByRole('link', {name: /View public results/}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('[data-result-applicant]').count(), 12);
    assert.equal(await page.locator('[data-result-recipient]').count(), 1);
    assert((await page.locator('[aria-label="Published recipient records"]').innerText()).includes(selectedReference));
    assert(!(await page.locator('main').innerText()).includes('Ana Testalpha'));
    await page.screenshot({path: path.join(output, 'public-results-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    const mobileLeft = await page.locator('section[aria-label="Submitted applications"]').boundingBox();
    const mobileRight = await page.locator('section[aria-label="Selected recipients"]').boundingBox();
    assert(mobileRight.y > mobileLeft.y);
    await page.screenshot({path: path.join(output, 'public-results-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('PASS browser: AHP approval, two program rankings, score breakdown, SELECT FOR ASSISTANCE, program grid, reviewed publication, masked names/full references, desktop columns and mobile stacking.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
