const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const output = path.join(__dirname, '../docs/registration-approval-2026-10-24/ui');
  fs.mkdirSync(output, {recursive:true});
  const checks = [], errors = [];
  try {
    const page = await browser.newPage();
    page.on('pageerror', error => errors.push(error.message));
    const responsive = async name => {
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width,height:1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${name}: overflow at ${width}`);
        assert.deepEqual(await page.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
          return ids.filter((id, i) => ids.indexOf(id) !== i);
        }), [], 'duplicate IDs');
        checks.push({name,width});
      }
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(() => document.activeElement !== document.body), true, 'keyboard focus');
    };
    await page.goto(process.env.QA_URL + '/accounts/login/');
    await page.locator('[name="username"]').fill(process.env.QA_USERNAME);
    await page.locator('[name="password"]').fill(process.env.QA_PASSWORD);
    await page.getByRole('button', {name:/sign in|log in/i}).click();
    await page.waitForURL(url => !url.pathname.includes('/login/'));
    const detail = `/membership/registrations/${process.env.QA_REFERENCE}/`;
    assert.equal((await page.goto(process.env.QA_URL + detail)).status(), 200);
    await page.getByRole('link', {name:'Prepare membership approval',exact:true}).click();
    await responsive('prepare');
    const data = JSON.parse(process.env.QA_DATA);
    for (const name of ['control_number','identity_basis','requirements_basis','assessor','assessed_on',
      'assessment_basis','control_number_basis','duplicate_review']) {
      await page.locator(`[name="${name}"]`).fill(data[name]);
    }
    await page.locator('[name="accepted"]').check();
    await page.locator(`[name="document_${process.env.QA_REQUIREMENT}"]`).setInputFiles({
      name:'synthetic.pdf', mimeType:'application/pdf', buffer:Buffer.from('%PDF-1.4\nSynthetic demonstration only\n')});
    assert.equal(await page.locator('[name="first_name"]').isDisabled(), true);
    await page.screenshot({path:path.join(output,'prepare-desktop.png'), fullPage:true});
    await page.getByRole('button', {name:'Save acceptance and prepare membership review',exact:true}).click();
    await page.waitForURL(process.env.QA_URL + detail);
    await responsive('decision');
    await page.locator('[name="verified"]').selectOption('yes');
    await page.locator('#verify_notes').fill('Synthetic manual registry review only. No government claim.');
    await page.getByRole('button', {name:'Save manual verification',exact:true}).click();
    await page.waitForLoadState('networkidle');
    await page.locator('[name="decision"]').selectOption('approved');
    await page.locator('#decision_notes').fill('Synthetic authorized decision for fictional member only.');
    await page.getByRole('button', {name:'Save membership decision',exact:true}).click();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.getByRole('link', {name:'Open official Member record',exact:true}).count(), 1);
    await responsive('approved');
    await page.screenshot({path:path.join(output,'approved-desktop.png'), fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(output,'approved-mobile.png'), fullPage:true});
    await page.getByRole('link', {name:'Open official Member record',exact:true}).click();
    assert.equal(await page.getByRole('heading', {name:'Synthetic Applicant',exact:true}).count(), 1);
    const anonymous = await browser.newContext();
    const response = await anonymous.request.get(process.env.QA_URL + detail, {maxRedirects:0});
    assert.equal(response.status(), 302);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output,'checks.json'), JSON.stringify({checks, errors,
      approvedMember:true, anonymousDenied:true, fixtureOnly:true},null,2));
    console.log('Synthetic pending -> onsite acceptance -> manual verification -> approved Member browser journey passed; 12 responsive/no-duplicate-ID checks and keyboard focus passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
