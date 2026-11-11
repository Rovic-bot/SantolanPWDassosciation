const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const output = path.join(__dirname, '../docs/registration-ui-2026-10-24/ui');
  fs.mkdirSync(output, {recursive:true});
  const checks = [], errors = [];
  const observe = page => page.on('pageerror', error => errors.push(error.message));
  const go = async (page, route) => {
    const response = await page.goto(process.env.QA_URL + route, {waitUntil:'networkidle'});
    assert.equal(response.status(), 200, route);
  };
  const responsive = async (page, name) => {
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({width,height:1000});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${name} overflow ${width}`);
      assert.deepEqual(await page.evaluate(() => {
        const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
        return ids.filter((id,index) => ids.indexOf(id) !== index);
      }), [], name + ' duplicate IDs');
      checks.push({name,width});
    }
    await page.evaluate(() => window.scrollTo(0, 0));
  };
  try {
    const applicant = await browser.newContext();
    const page = await applicant.newPage(); observe(page);
    await go(page, '/membership/register/');
    await page.getByRole('link', {name:'Start online membership registration',exact:true}).click();
    await page.waitForURL('**/membership/registration/apply/');
    assert.equal(await page.locator('[data-profile-field="suffix_other"]').isVisible(),false);
    await page.locator('[name="suffix"]').selectOption('other');
    assert.equal(await page.locator('[name="suffix_other"]').isEnabled(),true);
    assert.equal(await page.locator('[name="suffix_other"]').getAttribute('required'),'');
    await page.locator('[name="suffix"]').selectOption('');
    await page.locator('[name="no_middle_name"]').check();
    assert.equal(await page.locator('[name="middle_name"]').isDisabled(),true);
    await page.locator('[name="no_middle_name"]').uncheck();
    const data = JSON.parse(process.env.QA_FORM_DATA);
    for (const [name,value] of Object.entries(data)) {
      const field = page.locator(`[name="${name}"]`);
      if (!Array.isArray(value) && await field.isDisabled()) {
        assert.equal(String(value),'',`disabled ${name} must not discard entered data`);
        continue;
      }
      if (Array.isArray(value)) {
        for (const item of value) await page.locator(`[name="${name}"][value="${item}"]`).check();
      } else if (await field.getAttribute('type') === 'checkbox') {
        if (value) await field.check();
      } else if (await field.evaluate(node => node.tagName) === 'SELECT') {
        await field.selectOption(String(value));
      } else {
        await field.fill(String(value));
      }
    }
    assert.equal(await page.locator('[name="control_number"]').count(), 0);
    await page.setViewportSize({width:1440,height:1000});
    const publicLayout = await page.locator('.registration-editor').evaluate(editor => {
      const section = editor.querySelector('.profile-section');
      return {maxWidth:getComputedStyle(editor).maxWidth, padding:getComputedStyle(editor).padding,
        borderRadius:getComputedStyle(section).borderRadius,
        gap:getComputedStyle(section.querySelector('.profile-grid')).gap,
        columns:getComputedStyle(section.querySelector('.profile-grid')).gridTemplateColumns.split(' ').length};
    });
    assert.equal(publicLayout.columns,2,'public desktop two-column form');
    assert.equal(await page.locator('[data-profile-field="middle_name"] [name="no_middle_name"]').count(),1);
    await responsive(page, 'full-applicant-form');
    await page.screenshot({path:path.join(output,'public-full-form.png'),fullPage:true});
    await page.getByRole('button',{name:'Submit pending registration',exact:true}).focus();
    await page.keyboard.press('Enter');
    await page.waitForURL('**/membership/registration/receipt/');
    const reference = (await page.locator('.registration-reference strong').innerText()).trim();
    assert.match(reference,/^AMR-/);
    await responsive(page, 'complete-receipt');
    await page.screenshot({path:path.join(output,'reference-receipt.png'),fullPage:true});
    const staff = await browser.newContext();
    const admin = await staff.newPage(); observe(admin);
    await go(admin, '/accounts/login/');
    await admin.locator('[name="username"]').fill(process.env.QA_USERNAME);
    await admin.locator('[name="password"]').fill(process.env.QA_PASSWORD);
    await admin.locator('button[type="submit"]').click();
    await admin.waitForURL('**/dashboard/');
    await go(admin, '/membership/registrations/');
    assert.equal(await admin.getByRole('link',{name:reference,exact:true}).count(),1);
    await responsive(admin,'registration-monitoring');
    await admin.screenshot({path:path.join(output,'admin-inbox.png'),fullPage:true});
    await go(admin, '/membership/applications/new/');
    const adminLayout = await admin.locator('.record-editor').evaluate(editor => {
      const section = editor.querySelector('.profile-section');
      return {maxWidth:getComputedStyle(editor).maxWidth, padding:getComputedStyle(editor).padding,
        borderRadius:getComputedStyle(section).borderRadius,
        gap:getComputedStyle(section.querySelector('.profile-grid')).gap,
        columns:getComputedStyle(section.querySelector('.profile-grid')).gridTemplateColumns.split(' ').length};
    });
    assert.deepEqual(publicLayout, adminLayout, 'public uses the onsite editor dimensions and section grid');
    await admin.screenshot({path:path.join(output,'admin-onsite-comparison.png'),fullPage:true});
    await admin.getByLabel('Membership application reference number',{exact:true}).fill(reference);
    await admin.getByRole('button',{name:'Load online application',exact:true}).focus();
    await admin.keyboard.press('Enter');
    await admin.waitForURL(`**/membership/registrations/${reference}/`);
    assert.equal(await admin.locator('[name="submitted-first_name"]').inputValue(),'Synthetic');
    assert.equal(await admin.locator('[name="submitted-street"]').inputValue(),'Test Street');
    assert.equal(await admin.locator('[name="submitted-first_name"]').isDisabled(),true);
    assert.equal(await admin.locator('[name="submitted-disability_types"]:checked').count(),data.disability_types.length);
    await responsive(admin,'prefilled-private-application');
    await admin.screenshot({path:path.join(output,'admin-prefilled-form.png'),fullPage:true});
    await admin.setViewportSize({width:390,height:1000});
    await admin.evaluate(() => document.documentElement.style.fontSize='200%');
    await admin.screenshot({path:path.join(output,'admin-prefilled-mobile.png'),fullPage:true});
    assert.equal(await admin.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),false,'prefill enlarged text overflow');
    const unauthorized = await applicant.request.get(process.env.QA_URL + '/membership/registrations/load/?reference=' + reference, {maxRedirects:0});
    assert.equal(unauthorized.status(),302);
    await page.getByRole('button',{name:'Done — show my reference number',exact:true}).click();
    await page.getByRole('heading',{name:'Registration submitted',exact:true}).waitFor();
    assert.equal(await page.locator('.registration-reference').innerText(),reference);
    assert.equal((await applicant.request.get(process.env.QA_URL + '/membership/registration/receipt/')).status(),403);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'checks.json'),JSON.stringify({captured_utc:new Date().toISOString(),
      browser:browser.version(),policy:'SYNTHETIC ONLY; no operating approval',checks,
      onsite_layout_match:{public:publicLayout,admin:adminLayout},
      full_form_receipt_prefill:true,keyboard_submit_and_lookup:true,unauthorized_lookup_denied:true,
      finish_revocation:true,enlarged_text_200_percent:true,page_errors:errors},null,2));
    console.log(`PASS: full pending form -> receipt -> inbox -> onsite reference lookup -> prefilled same record; ${checks.length} responsive checks.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error.stack); process.exit(1); });
