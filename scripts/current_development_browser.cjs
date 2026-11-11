/* Read-only UI acceptance against the retained main development system. */
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const local = path.join(root, '.local/ewaf-twelve-demo');
const manifest = JSON.parse(fs.readFileSync(path.join(local, 'connection.json'), 'utf8'));
const fixtures = JSON.parse(fs.readFileSync(path.join(local, 'seed-summary.json'), 'utf8'));
assert.equal(manifest.purpose, 'EWAF_TWELVE_PERSISTENT_DEMO');
const origin = `http://127.0.0.1:${manifest.http_port}`;
const output = path.join(root, 'docs/main-development-cleanup-2026-10-27');
fs.mkdirSync(output, {recursive: true});
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const removed = ['Download private calculation (JSON)', 'Shared configuration',
  'Next ranking: approved Vault weight version', 'Review accepted-input rules',
  'Enter / verify EWAF information', 'Enter and verify EWAF information',
  'Decision history', 'Calculation history', 'EWAF DEMO — FICTIONAL DATA ONLY',
  'Fictional demonstration database.'];

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const health = await context.request.get(origin + '/ewaf-demo/health/');
    assert.equal((await health.json()).instance_id, manifest.instance_id);
    const home = await page.goto(origin + '/', {waitUntil: 'networkidle'});
    assert.equal(home.status(), 200);
    assert.equal(home.headers()['x-santolan-environment'], 'MAIN-DEVELOPMENT');
    assert(!(await page.locator('body').innerText()).includes('FICTIONAL DATA ONLY'));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(manifest.admin_username);
    await page.locator('[name=password]').fill(manifest.admin_password);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    for (const [index, scenario] of fixtures.scenarios.entries()) {
      const response = await page.goto(`${origin}/ewaf/programs/${scenario.program_id}/`, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      const body = await page.locator('body').innerText();
      for (const text of removed) assert(!body.includes(text), `${scenario.name}: ${text}`);
      assert.equal(await page.locator('#id_generate_reason').count(), 0);
      assert.equal(await page.locator('#calculate form [name=reason]').count(), 0);
      assert(await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).isEnabled());
      assert.equal(await page.locator('#results table tbody tr').count(), 12);
      if (index === 0) {
        await page.screenshot({path: path.join(output, 'ranking-desktop.png'), fullPage: true});
        await page.locator('#results').screenshot({path: path.join(output, 'ranking-results.png')});
        await page.setViewportSize({width: 390, height: 1000});
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.screenshot({path: path.join(output, 'ranking-mobile.png'), fullPage: true});
        await page.setViewportSize({width: 1440, height: 1100});
      }
    }
    const name = (await page.locator('#results table tbody tr').first().locator('th a').innerText()).trim();
    await page.locator('#results table tbody tr').first().locator('th a').click();
    await page.waitForLoadState('networkidle');
    assert(new URL(page.url()).pathname.endsWith('/breakdown/'));
    assert((await page.locator('main').innerText()).includes(name));
    assert(!(await page.locator('body').innerText()).includes('Fictional demonstration database.'));
    assert.equal(await page.getByText('Download private calculation (JSON)', {exact: true}).count(), 0);
    assert.deepEqual(errors, []);
    console.log('PASS: main environment identity, public home, dashboard login, five clean ranking pages, no generation reason field, 12 saved scores each, applicant scoring, desktop/mobile layout. No rankings or approvals changed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
