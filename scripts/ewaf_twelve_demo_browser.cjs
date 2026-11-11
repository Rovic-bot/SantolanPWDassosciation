/* Manual-demo acceptance: real login, all saved scenarios, one new calculation. */
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const local = path.join(root, '.local', 'ewaf-twelve-demo');
const manifest = JSON.parse(fs.readFileSync(path.join(local, 'connection.json'), 'utf8'));
const summary = JSON.parse(fs.readFileSync(path.join(local, 'seed-summary.json'), 'utf8'));
assert.equal(manifest.purpose, 'EWAF_TWELVE_PERSISTENT_DEMO');
assert.equal(manifest.state, 'ready');
const origin = `http://127.0.0.1:${manifest.http_port}`;
const output = path.join(root, 'docs', 'ewaf-twelve-demo-2026-10-27');
fs.mkdirSync(output, {recursive: true});
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const source = [
  [10000, 1, 1, 3, 2], [64000, 0, 4, 3, 2], [40000, 0, 1, 0, 2],
  [82000, 0, 1, 4, 10], [28000, 1, 1, 2, 4], [28000, 0, 1, 2, 4],
  [41500, 1, 1, 1, 6], [100000, 1, 1, 4, 1], [37000, 0, 1, 2, 5],
  [37000, 0, 1, 2, 5], [51000, 0, 1, 1, 7], [23500, 0, 1, 3, 8],
];
const ranks = {
  balanced: [10, 4, 5, 11, 6, 9, 1, 12, 7, 7, 2, 3],
  ses: [1, 10, 6, 11, 3, 5, 4, 12, 7, 7, 9, 2],
  es: [10, 1, 5, 11, 6, 9, 2, 12, 7, 7, 3, 4],
  pa: [10, 9, 1, 11, 4, 7, 2, 12, 5, 5, 3, 8],
  hm: [11, 9, 10, 1, 7, 8, 4, 12, 5, 5, 3, 2],
};

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin
      ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [], results = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/ewaf-demo/', {waitUntil: 'networkidle'});
    assert(new URL(page.url()).pathname.includes('login'));
    await page.locator('[name=username]').fill(manifest.admin_username);
    await page.locator('[name=password]').fill(manifest.admin_password);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/ewaf-demo/');
    assert.equal(await page.locator('tbody tr').count(), 5);
    assert((await page.locator('body').innerText()).includes('FICTIONAL DATA ONLY'));
    await page.screenshot({path: path.join(output, 'demo-programs.png'), fullPage: true});
    for (const item of summary.scenarios) {
      const response = await page.goto(`${origin}/ewaf/programs/${item.program_id}/`, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert.equal(response.headers()['x-santolan-environment'], 'EWAF-TWELVE-DEMO');
      const rows = page.locator('#results table tbody tr');
      assert.equal(await rows.count(), 12);
      assert.equal(await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).isEnabled(), true);
      for (const row of await rows.all()) {
        const name = (await row.locator('th a').innerText()).trim();
        const index = summary.members.findIndex(member => member.name === name);
        assert(index >= 0, name);
        const [income, p, employment, pa, hm] = source[index];
        const normalized = [(100000 - income) / 90000 * (.9 + .1 * p),
          (employment - 1) / 3, (4 - pa) / 4, (hm - 1) / 9];
        const focused = ['ses', 'es', 'pa', 'hm'].indexOf(item.scenario);
        const score = 100 * normalized.reduce((sum, value, column) => sum + value *
          (focused < 0 ? .25 : column === focused ? .625 : .125), 0);
        const cells = await row.locator('td').allTextContents();
        assert.equal(parseInt(cells[0], 10), ranks[item.scenario][index], `${item.name}: ${name}`);
        assert.equal(cells[1].trim(), score.toFixed(2), `${item.name}: ${name}`);
      }
      await page.locator('#results').screenshot({path: path.join(output, `${item.scenario}-ranking.png`)});
      results.push({scenario: item.name, rows: 12, scores_and_ranks: 'passed', generation_enabled: true});
    }
    const balanced = summary.scenarios.find(item => item.primary);
    await page.goto(`${origin}/ewaf/programs/${balanced.program_id}/`, {waitUntil: 'networkidle'});
    const before = await page.locator('#results details a').count();
    await page.locator('#id_generate_reason').fill('SYNTHETIC demo browser acceptance: save another Balanced calculation.');
    await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes(balanced.program_id)),
      page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).click(),
    ]);
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('#results details a').count(), before + 1);
    assert.equal(await page.locator('#results table tbody tr').count(), 12);
    await page.setViewportSize({width: 390, height: 1000});
    await page.goto(origin + '/ewaf-demo/', {waitUntil: 'networkidle'});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'demo-programs-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({login: 'passed',
      anonymous_redirect: 'passed', scenarios: results, balanced_saved_again: true,
      mobile_width: 390, javascript_errors: errors}, null, 2));
    console.log('PASS: real login, 60 scores/ranks, five enabled generation controls, saved Balanced calculation, mobile layout.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exit(1);});
