/* Retained development verification: reads and unsaved AHP previews only. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const local = path.join(root, '.local/ewaf-twelve-demo');
const manifest = JSON.parse(fs.readFileSync(path.join(local, 'connection.json'), 'utf8'));
const fixtures = JSON.parse(fs.readFileSync(path.join(local, 'seed-summary.json'), 'utf8'));
assert.equal(manifest.purpose, 'EWAF_TWELVE_PERSISTENT_DEMO');
const origin = `http://127.0.0.1:${manifest.http_port}`;
const output = path.join(root, 'docs/applicant-vault-2026-10-27');
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
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(manifest.admin_username);
    await page.locator('[name=password]').fill(manifest.admin_password);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    const program = fixtures.scenarios.find(row => row.scenario === 'hm').program_id;
    await page.goto(`${origin}/programs/manage/${program}/applications/`, {waitUntil: 'networkidle'});
    await page.getByRole('link', {name: 'Iris Testindia', exact: true}).click();
    await page.waitForLoadState('networkidle');
    const info = page.locator('#household-information');
    const values = await info.locator('dl > div').evaluateAll(rows => Object.fromEntries(
      rows.map(row => [row.querySelector('dt').textContent, row.querySelector('dd').childNodes[0].textContent.trim()])));
    assert.deepEqual(values, {'Monthly household income': 'PHP 37,000.00', 'Number of household members': '5',
      'Employment status': 'Full-Time Worker', 'Household 4Ps participation': 'Verified No', 'Previous assistance received': '2'});
    assert(!(await info.innerText()).includes('EWAF'));
    assert((await page.locator('#overview').innerText()).includes('Family information'));
    assert(await page.locator('#program-requirements').evaluate(element => element.open));
    await page.screenshot({path: path.join(output, 'current-applicant-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await info.screenshot({path: path.join(output, 'current-applicant-mobile.png')});
    await page.setViewportSize({width: 1440, height: 1100});
    await page.goto(origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
    assert.equal(await page.locator('button[value=DRAFT]').count(), 0);
    await page.waitForFunction(() => !document.querySelector('button[value=LOCKED]').disabled);
    assert((await page.locator('#weight-status').innerText()).includes('Calculated weights are ready'));
    assert(!(await page.locator('#weight-status').innerText()).includes('precision'));
    await page.screenshot({path: path.join(output, 'current-vault-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'current-vault-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    assert.deepEqual(blocked, []);
    console.log('PASS: current Iris applicant values 37000 / 5 / Full-Time Worker / Verified No / 2; shared member profile; visible program requirements; desktop/mobile; saved proposal previews successfully and approval enabled without Save weight draft. No records or approvals changed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
