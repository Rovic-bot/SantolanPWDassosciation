/* Main retained development: readiness/preview reads only; no ranking writes. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const local = path.join(root, '.local/ewaf-twelve-demo');
const manifest = JSON.parse(fs.readFileSync(path.join(local, 'connection.json'), 'utf8'));
const fixtures = JSON.parse(fs.readFileSync(path.join(local, 'seed-summary.json'), 'utf8'));
assert.equal(manifest.purpose, 'EWAF_TWELVE_PERSISTENT_DEMO');
const origin = `http://127.0.0.1:${manifest.http_port}`;
const output = path.join(root, 'docs/ewaf-reranking-2026-10-27');
fs.mkdirSync(output, {recursive: true});
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    const blocked = [];
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin) return route.abort();
      if (!['GET', 'HEAD'].includes(request.method())) {
        const allowed = request.method() === 'POST' && (url.pathname === '/accounts/login/' ||
          url.pathname === '/ewaf/vault/' && (request.postData() || '').includes('name="action"\r\n\r\nPREVIEW_WEIGHTS'));
        if (!allowed) { blocked.push(url.pathname); return route.abort(); }
      }
      return route.continue();
    });
    const health = await context.request.get(origin + '/ewaf-demo/health/');
    assert.equal((await health.json()).instance_id, manifest.instance_id);
    const page = await context.newPage(), errors = [], checks = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(manifest.admin_username);
    await page.locator('[name=password]').fill(manifest.admin_password);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    for (const row of fixtures.scenarios) {
      await page.goto(`${origin}/ewaf/programs/${row.program_id}/`, {waitUntil: 'networkidle'});
      assert(await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).isEnabled());
      assert(!(await page.locator('main').innerText()).includes('Scoring settings are incomplete'));
      if (row.scenario === 'hm') {
        const ben = page.locator('#results table tbody tr').filter({hasText: 'Ben Testbravo'});
        assert((await ben.innerText()).includes('Assistance received'));
        assert.equal(await ben.getByRole('button', {name: 'SELECT FOR ASSISTANCE', exact: true}).count(), 0);
        await page.screenshot({path: path.join(output, 'current-hm-ready.png'), fullPage: true});
      }
      checks.push({scenario: row.scenario, generation_enabled: true});
    }
    await page.goto(origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
    assert.equal(await page.locator('button[value=DRAFT]').count(), 0);
    await page.waitForFunction(() => !document.querySelector('button[value=LOCKED]').disabled);
    await page.screenshot({path: path.join(output, 'current-vault-ready.png'), fullPage: true});
    assert.deepEqual(blocked, []);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'current-readiness.json'), JSON.stringify({checks, approval_enabled: true,
      business_writes: 0, browser_errors: errors}, null, 2));
    console.log('PASS retained development: Generate EWAF Ranking enabled in all five programs; confirmed recipient protected; Vault approval ready without draft; no ranking/approval/selection/publication writes.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
