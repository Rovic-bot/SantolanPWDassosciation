const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const out = path.join(__dirname, '../docs/dual-registration-2026-10-24');
  fs.mkdirSync(out, {recursive: true});
  const errors = [], checks = [];
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  const go = async route => {
    const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
    assert.equal(response.status(), 200, route);
    return response;
  };
  const responsive = async name => {
    for (const width of [320, 390, 768, 1280, 1440]) {
      await page.setViewportSize({width, height: 1000});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${name} overflow ${width}`);
      assert.deepEqual(await page.evaluate(() => {
        const ids = [...document.querySelectorAll('[id]')].map(n => n.id);
        return ids.filter((id, i) => ids.indexOf(id) !== i);
      }), [], name + ' duplicate IDs');
      checks.push({name, width});
    }
  };
  const fill = async data => {
    for (const [name, value] of Object.entries(data)) {
      const field = page.locator(`[name="${name}"]`);
      if (Array.isArray(value)) {
        for (const option of value) await page.locator(`[name="${name}"][value="${option}"]`).check();
      } else if (await field.getAttribute('type') === 'checkbox') {
        if (value) await field.check();
      } else if (await field.evaluate(n => n.tagName) === 'SELECT') {
        await field.selectOption(String(value));
      } else await field.fill(String(value));
    }
  };
  const printCheck = async name => {
    await page.evaluate(() => {window.printCalls = 0; window.print = () => window.printCalls++;});
    await page.locator('[data-registration-print]').click();
    assert.equal(await page.evaluate(() => window.printCalls), 1);
    await page.emulateMedia({media: 'print'});
    assert.equal(await page.locator('.site-header').isVisible(), false);
    assert.equal(await page.locator('.registration-controls').first().isVisible(), false);
    await page.screenshot({path: path.join(out, name + '-print.png'), fullPage: true});
    await page.emulateMedia({media: 'screen'});
    checks.push({name, print: true});
  };
  try {
    await go('/');
    await responsive('home');
    assert.equal(await page.getByRole('heading', {name: 'Online Registration with In-Person Verification'}).count(), 1);
    await go('/membership/register/');
    await responsive('guidance');
    await page.screenshot({path: path.join(out, 'guidance-desktop.png'), fullPage: true});
    await go('/membership/registration/apply/');
    await responsive('association-form');
    assert.equal(await page.locator('[name="income_category"]').count(), 0);
    assert.equal(await page.locator('[name="family_members"]').count(), 1);
    await fill(JSON.parse(process.env.QA_ASSOCIATION));
    await page.locator('[name="birthdate"]').blur();
    assert.match(await page.locator('[data-registration-age]').textContent(), /years/);
    await page.setViewportSize({width: 390, height: 1000});
    await page.screenshot({path: path.join(out, 'association-mobile.png'), fullPage: true});
    await page.getByRole('button', {name: 'Submit pending registration', exact: true}).click();
    await page.waitForURL('**/membership/registration/receipt/');
    const reference = (await page.locator('.registration-reference').textContent()).trim();
    assert.match(reference, /^AMR-/);
    await responsive('association-receipt');
    await printCheck('association');
    const outsider = await browser.newContext();
    const denied = await outsider.request.get(process.env.QA_URL + '/membership/registration/receipt/');
    assert.ok([403, 404].includes(denied.status()));
    await outsider.close();
    await page.getByRole('button', {name: 'Done — show my reference number'}).click();
    const pdaoPage = await go('/membership/registration/pdao/');
    assert.equal(pdaoPage.headers()['referrer-policy'], 'same-origin');
    await responsive('pdao-form');
    await fill(JSON.parse(process.env.QA_PDAO));
    const [pdaoPost] = await Promise.all([
      page.waitForRequest(request => request.method() === 'POST' && new URL(request.url()).pathname === '/membership/registration/pdao/'),
      page.getByRole('button', {name: 'Submit and prepare printable PDAO form'}).click()
    ]);
    assert.equal(pdaoPost.headers().origin, new URL(process.env.QA_URL).origin);
    await page.getByRole('status').filter({hasText: 'Your PDAO form is ready to print'}).waitFor();
    assert.equal(await page.locator('.registration-reference').count(), 0);
    assert.match(await page.locator('#main-content').textContent(), /Visual Disability, Physical Disability/);
    await responsive('pdao-print');
    await printCheck('pdao');
    await page.getByRole('link', {name: 'Finish and return to guidance'}).click();
    await go('/membership/registration/pdao/');
    assert.equal(await page.locator('[name="first_name"]').inputValue(), '');
    await go('/accounts/login/');
    await page.locator('[name="username"]').fill(process.env.QA_USERNAME);
    await page.locator('[name="password"]').fill(process.env.QA_PASSWORD);
    await page.locator('form button[type="submit"]').click();
    await page.waitForURL(url => !url.pathname.includes('/accounts/login/'));
    await go('/membership/registrations/' + reference + '/');
    assert.equal(await page.locator('[name="submitted-family_members"]').inputValue(), '6');
    assert.equal(await page.locator('[name="submitted-family_members"]').isDisabled(), true);
    assert.match(await page.locator('#main-content').textContent(), /Four \(4\) photocopies of PWD ID/);
    await page.screenshot({path: path.join(out, 'staff-review.png'), fullPage: true});
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(out, 'browser-checks.json'), JSON.stringify({checks, errors}, null, 2));
    console.log(JSON.stringify({responsiveChecks: checks.filter(c => c.width).length, printChecks: 2, errors}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
