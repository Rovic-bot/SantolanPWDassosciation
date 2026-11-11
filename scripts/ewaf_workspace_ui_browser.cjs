/* Synthetic services plus the requested ranking, review drawer and breakdown UI. */
const path = require('path'), fs = require('fs'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  assert(process.env.G12_ARTIFACT_DIR, 'Verified disposable MySQL launcher required');
  const origin = new URL(process.env.QA_URL).origin;
  assert(['127.0.0.1','localhost'].includes(new URL(origin).hostname));
  assert(!['8000','8012'].includes(new URL(origin).port));
  const out = path.join(process.env.G12_ARTIFACT_DIR, 'ewaf-workspace-ui');
  fs.mkdirSync(out, {recursive: true});
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1560, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(process.env.QA_USERNAME);
    await page.locator('[name=password]').fill(process.env.QA_PASSWORD);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    const workspace = `${origin}/ewaf/programs/${process.env.QA_PROGRAM}/`;
    await page.goto(workspace, {waitUntil: 'networkidle'});
    await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).click();
    await page.waitForLoadState('networkidle');
    const rows = page.locator('.ewaf-ranking-table tbody tr[data-applicant]');
    assert.equal(await rows.count(), 12);
    assert.equal(await page.locator('.workspace-module').count(), 8);
    assert.equal(await page.locator('.workspace-module[open]').count(), 1);
    assert.equal(await page.locator('.ewaf-summary article').count(), 3);
    const snapshot = await rows.evaluateAll(items => items.map(row => ({id: row.dataset.applicant,
      rank: row.querySelector('.ewaf-rank').textContent.trim(), score: row.querySelector('.ewaf-score-link strong').textContent})));
    const ana = rows.filter({hasText: 'Ana Testalpha'}), ben = rows.filter({hasText: 'Ben Testbravo'});
    assert((await ben.innerText()).includes('Assistance received'));
    await page.screenshot({path: path.join(out, 'ranking-desktop.png'), fullPage: true});
    const search = page.locator('#ranking-filters [name=q]');
    await search.fill('Iris');
    await page.waitForFunction(() => document.querySelector('#ranking-body').dataset.count === '1');
    assert.equal(await rows.count(), 1);
    assert((await rows.innerText()).includes('Iris Testindia'));
    const filtered = await rows.evaluate(row => ({id: row.dataset.applicant,
      rank: row.querySelector('.ewaf-rank').textContent.trim(), score: row.querySelector('.ewaf-score-link strong').textContent}));
    assert.deepEqual(filtered, snapshot.find(row => row.id === filtered.id));
    await search.fill('');
    await page.waitForFunction(() => document.querySelector('#ranking-body').dataset.count === '12');
    await page.locator('#ranking-filters [name=decision]').selectOption('received');
    await page.waitForFunction(() => document.querySelector('#ranking-body').dataset.count === '1');
    assert((await rows.innerText()).includes('Ben Testbravo'));
    await page.locator('#ranking-filters [name=decision]').selectOption('');
    await page.waitForFunction(() => document.querySelector('#ranking-body').dataset.count === '12');
    assert.deepEqual(await rows.evaluateAll(items => items.map(row => ({id: row.dataset.applicant,
      rank: row.querySelector('.ewaf-rank').textContent.trim(), score: row.querySelector('.ewaf-score-link strong').textContent}))), snapshot);
    const review = ana.getByRole('link', {name: 'Review Ana Testalpha', exact: true});
    const beforeUrl = page.url();
    await review.click();
    const drawer = page.locator('dialog:modal');
    await drawer.waitFor();
    assert.equal(page.url(), beforeUrl);
    assert((await drawer.innerText()).includes('10,000 / month'));
    for (const value of ['Verified Yes', 'Full-Time Worker', '3 records', '2 people', process.env.QA_REFERENCE]) {
      assert((await drawer.innerText()).includes(value), value);
    }
    assert(await drawer.locator('h2').evaluate(el => document.activeElement === el));
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('Tab');
      assert(await drawer.evaluate(el => el.contains(document.activeElement)));
    }
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('dialog:modal'));
    assert(await review.evaluate(el => document.activeElement === el));
    await review.click();
    await page.screenshot({path: path.join(out, 'applicant-drawer-desktop.png'), fullPage: true});
    await drawer.getByRole('link', {name: 'Score breakdown', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.getByRole('heading', {name: 'Score breakdown', exact: true}).count(), 1);
    assert.equal(await page.locator('[data-points-criterion]').count(), 4);
    assert.equal(await page.locator('.ewaf-comparison-table tbody tr').count(), 12);
    assert.equal(await page.locator('.ewaf-person-score h2').innerText(), 'Ana Testalpha');
    assert((await page.locator('.ewaf-detail-table').innerText()).includes('62.50%'));
    assert(!(await page.locator('.ewaf-formulas').evaluate(el => el.open)));
    await page.screenshot({path: path.join(out, 'score-breakdown-desktop.png'), fullPage: true});
    await page.locator('.ewaf-formulas > summary').click();
    assert((await page.locator('.ewaf-formula-body').innerText()).includes('no second normalization'));
    const irisId = await page.locator('#breakdown-applicant option').filter({hasText: 'Iris Testindia'}).getAttribute('value');
    await Promise.all([
      page.waitForURL(url => url.searchParams.get('applicant') === irisId),
      page.locator('#breakdown-applicant').selectOption(irisId)
    ]);
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('.ewaf-person-score h2').innerText(), 'Iris Testindia');
    await page.getByRole('link', {name: 'Review applicant', exact: true}).click();
    await page.waitForLoadState('networkidle');
    await page.locator('dialog:modal').waitFor();
    assert((await page.locator('dialog:modal').innerText()).includes('Iris Testindia'));
    await page.keyboard.press('Escape');
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(out, 'ranking-mobile.png'), fullPage: true});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await ana.getByRole('link', {name: 'Review Ana Testalpha', exact: true}).click();
    await page.locator('dialog:modal').waitFor();
    const box = await page.locator('dialog:modal').boundingBox();
    assert(box.x >= 0 && box.x + box.width <= 391 && box.height <= 845);
    await page.locator('dialog:modal .selection-form button').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(out, 'applicant-drawer-mobile.png')});
    await page.getByRole('button', {name: 'Select for assistance', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert((await ana.innerText()).includes('Selected for assistance'));
    assert((await page.locator('.ewaf-summary article').nth(1).innerText()).includes('2'));
    await ben.getByRole('link', {name: 'Review Ben Testbravo', exact: true}).click();
    assert.equal(await page.locator('dialog:modal').getByRole('button', {name: 'Select for assistance', exact: true}).count(), 0);
    await page.keyboard.press('Escape');
    await page.getByRole('link', {name: 'Score breakdown', exact: true}).first().click();
    await page.waitForLoadState('networkidle');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(out, 'score-breakdown-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('PASS UI browser: saved ranking generation, whole-pool search/filter invariance, drawer data, keyboard/focus/Escape, score breakdown, applicant switching, mobile drawer, selection and completed-recipient protection, eight navigation groups.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
