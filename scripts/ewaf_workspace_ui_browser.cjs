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
    assert.equal(await page.locator('#ranking-body').getAttribute('data-total'), '12');
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
    const review = ana.locator('[data-applicant-open]');
    await review.focus();
    await page.keyboard.press('Enter');
    const panel = page.locator('#readiness');
    await panel.waitFor();
    assert.equal(new URL(page.url()).searchParams.get('review'), await ana.getAttribute('data-applicant'));
    assert(await panel.evaluate(el => document.activeElement === el));
    for (const [code, value] of [['SES', '10000'], ['ES', 'Employed'], ['PA', '3'], ['HM', '2']]) {
      assert((await panel.locator(`[data-criterion="${code}"]`).innerText()).replaceAll(',', '').includes(value), code);
    }
    assert.match((await panel.locator('[data-criterion="SES"] .ewaf-input-detail').innerText()).replace(/\s+/g, ' '), /4Ps.*Yes/);
    assert((await panel.innerText()).includes(process.env.QA_REFERENCE));
    await page.keyboard.press('Tab');
    assert(await panel.evaluate(el => el.contains(document.activeElement)));
    await page.screenshot({path: path.join(out, 'applicant-panel-desktop.png'), fullPage: true});
    await ana.locator('.ewaf-score-link').click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.getByRole('heading', {name: 'Score breakdown', exact: true}).count(), 1);
    assert.equal(await page.locator('[data-points-criterion]').count(), 4);
    assert.equal(await page.locator('.ewaf-comparison-table tbody tr').count(), 12);
    assert.equal(await page.locator('#applicant-score-card [data-score-name]').innerText(), 'Ana Testalpha');
    assert((await page.locator('.ewaf-detail-table').innerText()).includes('62.50%'));
    assert(!(await page.locator('.ewaf-formulas').evaluate(el => el.open)));
    await page.screenshot({path: path.join(out, 'score-breakdown-desktop.png'), fullPage: true});
    await page.locator('.ewaf-formulas > summary').click();
    assert((await page.locator('.ewaf-formula-body').innerText()).includes('Full-precision calculation details'));
    const irisId = await page.locator('#breakdown-applicant option').filter({hasText: 'Iris Testindia'}).getAttribute('value');
    await page.locator('#breakdown-applicant').selectOption(irisId);
    await page.waitForFunction(() => document.querySelector('#applicant-score-card [data-score-name]')?.textContent.trim() === 'Iris Testindia');
    assert.equal(await page.locator('#applicant-score-card [data-score-name]').innerText(), 'Iris Testindia');
    await page.locator('.ewaf-tabs').getByRole('link', {name: /^Ranking/}).click();
    await page.waitForLoadState('networkidle');
    await rows.filter({hasText: 'Iris Testindia'}).locator('[data-applicant-open]').click();
    assert((await panel.innerText()).includes('Iris Testindia'));
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(out, 'ranking-mobile.png'), fullPage: true});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await ana.locator('[data-applicant-open]').click();
    const box = await panel.boundingBox();
    assert(box.x >= 0 && box.x + box.width <= 391);
    await panel.locator('.selection-form button').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(out, 'applicant-panel-mobile.png')});
    await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' &&
        new URL(response.url()).pathname === `/ewaf/programs/${process.env.QA_PROGRAM}/`),
      panel.getByRole('button', {name: 'Select for assistance', exact: true}).click()
    ]);
    await page.waitForFunction(() => !document.querySelector('#readiness')?.hasAttribute('aria-busy'));
    assert((await ana.innerText()).includes('Selected for assistance'), await panel.innerText());
    assert.equal(await rows.locator('.ewaf-decision-selected, .ewaf-decision-received').count(), 2);
    await ben.locator('[data-applicant-open]').click();
    assert.equal(await panel.getByRole('button', {name: 'Select for assistance', exact: true}).count(), 0);
    await ana.locator('.ewaf-score-link').click();
    await page.waitForLoadState('networkidle');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(out, 'score-breakdown-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    console.log('PASS UI browser: saved ranking generation, whole-pool search/filter invariance, panel inputs, keyboard activation and focus, score breakdown, applicant switching, mobile panel, selection and completed-recipient protection, eight navigation groups.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
