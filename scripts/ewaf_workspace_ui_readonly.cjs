/* Verified retained development UI, with all business POSTs blocked. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const root = path.resolve(__dirname, '..'), local = path.join(root, '.local/ewaf-twelve-demo');
const manifest = JSON.parse(fs.readFileSync(path.join(local, 'connection.json'), 'utf8'));
const fixtures = JSON.parse(fs.readFileSync(path.join(local, 'seed-summary.json'), 'utf8'));
assert.equal(manifest.purpose, 'EWAF_TWELVE_PERSISTENT_DEMO');
const origin = `http://127.0.0.1:${manifest.http_port}`;
const output = path.join(root, 'docs/ewaf-workspace-ui-2026-10-27');
fs.mkdirSync(output, {recursive: true});
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1560, height: 1100}, reducedMotion: 'reduce'});
    const blocked = [], errors = [];
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin) return route.abort();
      if (!['GET','HEAD'].includes(request.method()) && !(request.method() === 'POST' && url.pathname === '/accounts/login/')) {
        blocked.push(url.pathname); return route.abort();
      }
      return route.continue();
    });
    assert.equal((await (await context.request.get(origin + '/ewaf-demo/health/')).json()).instance_id, manifest.instance_id);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(manifest.admin_username);
    await page.locator('[name=password]').fill(manifest.admin_password);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    const program = fixtures.scenarios.find(row => row.scenario === 'pa').program_id;
    const workspace = `${origin}/ewaf/programs/${program}/`;
    await page.goto(workspace, {waitUntil: 'networkidle'});
    assert(await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).isEnabled());
    assert.equal(await page.locator('.ewaf-ranking-table tbody tr[data-applicant]').count(), 12);
    assert.equal(await page.locator('.workspace-module').count(), 8);
    await page.screenshot({path: path.join(output, 'ranking-desktop.png'), fullPage: true});
    await page.getByRole('link', {name: 'Review Ana Testalpha', exact: true}).click();
    const drawer = page.locator('dialog:modal');
    await drawer.waitFor();
    for (const value of ['10,000 / month','Verified Yes','3 records','2 people']) assert((await drawer.innerText()).includes(value));
    await page.screenshot({path: path.join(output, 'applicant-review-desktop.png')});
    await drawer.getByRole('link', {name: 'Score breakdown', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('[data-points-criterion]').count(), 4);
    assert.equal(await page.locator('.ewaf-comparison-table tbody tr').count(), 12);
    await page.screenshot({path: path.join(output, 'score-breakdown-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'score-breakdown-mobile.png'), fullPage: true});
    await page.getByRole('link', {name: 'Review applicant', exact: true}).click();
    await page.waitForLoadState('networkidle');
    await page.locator('dialog:modal').waitFor();
    await page.locator('dialog:modal .selection-form button').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(output, 'applicant-review-mobile.png')});
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('dialog:modal'));
    await page.screenshot({path: path.join(output, 'ranking-mobile.png'), fullPage: true});
    const overflow = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > innerWidth + 1)
        .slice(0, 12).map(el => ({tag: el.tagName, classes: el.className, right: el.getBoundingClientRect().right}))}));
    assert(overflow.scroll <= overflow.width + 1, JSON.stringify(overflow));
    const ordinarySize = await page.locator('.ewaf-applicant-name').first().evaluate(el => parseFloat(getComputedStyle(el).fontSize));
    await page.getByRole('button', {name: 'Display preferences', exact: true}).click();
    await page.locator('[data-preference=text]').selectOption('largest');
    await page.locator('[data-preference=contrast]').check();
    await page.getByRole('button', {name: 'Close display preferences', exact: true}).click();
    const largerSize = await page.locator('.ewaf-applicant-name').first().evaluate(el => parseFloat(getComputedStyle(el).fontSize));
    assert(largerSize > ordinarySize);
    assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).getPropertyValue('--muted').trim()), '#253e43');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.getByRole('button', {name: 'Display preferences', exact: true}).click();
    await page.getByRole('button', {name: 'Reset preferences', exact: true}).click();
    await page.getByRole('button', {name: 'Close display preferences', exact: true}).click();
    assert.deepEqual(errors, []);
    assert.deepEqual(blocked, []);
    console.log('PASS main development read-only UI: ranking, Ana accepted inputs, drawer, contribution breakdown, comparison, desktop/mobile, larger text/high contrast, eight modules, no business writes or JavaScript errors.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
