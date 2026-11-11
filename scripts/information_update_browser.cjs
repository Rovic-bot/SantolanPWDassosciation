/* Synthetic rendered form; intercept submissions so no backend data is changed. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const html = fs.readFileSync(process.argv[2], 'utf8');
assert.ok(html.includes('My employment information has changed.') && html.includes('Fictional Example'));
const application = html.match(/\/programs\/manage\/[^/]+\/applications\/([^/]+)\//)[1];
const routePath = '/programs/manage/information/' + application + '/';
const origin = 'http://127.0.0.1:8013';
const output = path.resolve(__dirname, '../docs/information-update-2026-10-29');
fs.mkdirSync(output, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    const errors = [], blocked = [], submissions = [];
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin) {blocked.push(url.href); return route.abort();}
      if (url.pathname === routePath) {
        if (request.method() === 'POST') {
          const values = new URLSearchParams(request.postData());
          assert.equal(values.get('employment_status'), 'self_employed');
          assert.equal(values.get('notes'), '');
          assert.ok(values.get('expected'));
          assert.equal(values.has('evidence'), false);
          submissions.push('profile_edit');
        } else assert.equal(request.method(), 'GET');
        return route.fulfill({status: 200, contentType: 'text/html', body: html});
      }
      if (request.method() === 'GET' && url.pathname.startsWith('/static/')) return route.continue();
      blocked.push(url.pathname); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + routePath, {waitUntil: 'networkidle'});
    assert.equal(await page.locator('#reported-change-heading').isVisible(), true);
    assert.equal(await page.locator('[name=evidence]').count(), 0);
    assert.equal(await page.locator('[name=notes]').getAttribute('required'), null);
    assert.equal(await page.locator('[name=employment_status]').inputValue(), 'unemployed');
    await page.screenshot({path: path.join(output, 'report-desktop.png')});
    await page.locator('[name=employment_status]').selectOption('self_employed');
    await page.locator('[name=employment_status]').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(output, 'edit-desktop.png')});
    assert.equal(await page.locator('#reported-information-form').evaluate(form => form.reportValidity()), true);
    await Promise.all([page.waitForNavigation({waitUntil: 'networkidle'}),
      page.getByRole('button', {name: 'Save reviewed information', exact: true}).click()]);
    assert.deepEqual(submissions, ['profile_edit']);
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({width, height: 1000});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      if (width === 390) {
        await page.locator('[name=employment_status]').scrollIntoViewIfNeeded();
        await page.screenshot({path: path.join(output, 'edit-mobile.png')});
      }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(blocked, []);
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({
      synthetic_fixture: true, reported_change_visible: true, prefilled_editable_fields: true,
      evidence_picker_removed: true, optional_remarks: true, intercepted_submissions: submissions,
      backend_mutations: 0, responsive_widths: [320, 390, 768, 1440], page_errors: errors
    }, null, 2));
    console.log('PASS: reported change, editable prefilled profile, optional remarks, intercepted save and four responsive widths; no backend mutations.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
