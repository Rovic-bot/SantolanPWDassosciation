/* Mutating journey restricted to the verified disposable test runner. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  assert(process.env.G12_ARTIFACT_DIR, 'Use the isolated MySQL runner.');
  const origin = new URL(process.env.QA_URL).origin;
  assert(['localhost', '127.0.0.1'].includes(new URL(origin).hostname));
  const output = path.join(process.env.G12_ARTIFACT_DIR, 'applicant-vault');
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/accounts/login/', {waitUntil: 'networkidle'});
    await page.locator('[name=username]').fill(process.env.QA_USERNAME);
    await page.locator('[name=password]').fill(process.env.QA_PASSWORD);
    await page.locator('form button[type=submit]').click();
    await page.waitForURL(origin + '/dashboard/');
    await page.goto(`${origin}/programs/manage/${process.env.QA_PROGRAM}/applications/${process.env.QA_APPLICANT}/`, {waitUntil: 'networkidle'});
    const info = page.locator('#household-information');
    assert((await info.innerText()).includes('PHP 37,000.00'));
    assert((await info.innerText()).includes('Verified No'));
    assert((await info.innerText()).includes('Full-Time Worker'));
    assert(!(await info.innerText()).includes('EWAF'));
    assert((await page.locator('#overview').innerText()).includes('Family information'));
    assert(await page.locator('#program-requirements').evaluate(element => element.open));
    await page.screenshot({path: path.join(output, 'applicant-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await info.screenshot({path: path.join(output, 'applicant-mobile.png')});
    await page.setViewportSize({width: 1440, height: 1100});
    await page.goto(origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
    assert.equal(await page.locator('button[value=DRAFT]').count(), 0);
    for (const value of ['60', '65']) {
      await page.locator('#weight-HM').evaluate((input, value) => {
        input.value = value;
        input.dispatchEvent(new Event('input', {bubbles: true}));
      }, value);
      await page.locator('#preview-weights').click();
      await page.waitForFunction(() => {
        const form = document.querySelector('#ewaf-configuration-form');
        return form.elements.weight_review.value && !form.querySelector('button[value=LOCKED]').disabled;
      });
      await page.locator('[name=reason]').fill('SYNTHETIC repeated approval through the visible editor.');
      await page.locator('button[value=LOCKED]').click();
      await page.waitForLoadState('networkidle');
      assert((await page.locator('main').innerText()).includes('Configuration approved.'));
      assert.equal(await page.locator('button[value=DRAFT]').count(), 0);
    }
    await page.screenshot({path: path.join(output, 'vault-approved-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(output, 'vault-approved-mobile.png'), fullPage: true});
    await page.goto(`${origin}/ewaf/programs/${process.env.QA_PROGRAM}/`, {waitUntil: 'networkidle'});
    await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('#results table tbody tr').count(), 12);
    assert.deepEqual(errors, []);
    console.log('PASS: applicant profile, reviewed household values, visible requirements, desktop/mobile, repeated Calculate -> Approve without draft, and existing-program ranking.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
