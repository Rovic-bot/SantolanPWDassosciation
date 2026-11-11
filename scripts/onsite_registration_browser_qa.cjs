const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.connectOverCDP(process.env.QA_BROWSER_URL);
  const errors = [], checks = [];
  const output = process.env.QA_OUTPUT;
  try {
    const publicContext = await browser.newContext();
    const adminContext = await browser.newContext();
    await adminContext.route('https://registry.example.test/**', route => route.fulfill({
      contentType: 'text/html', body: '<p>Synthetic registry stand-in. No real verification performed.</p>'}));
    await adminContext.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION,
      url: process.env.QA_URL, httpOnly: true, sameSite: 'Lax'}]);
    const publicPage = await publicContext.newPage();
    const onsite = await adminContext.newPage();
    for (const page of [publicPage, onsite]) page.on('pageerror', error => errors.push(error.message));
    const responsive = async (page, name, theme = '') => {
      for (const width of [1600, 1280, 768, 390, 320]) {
        await page.setViewportSize({width, height: 900});
        await page.evaluate(async () => {
          await document.fonts.ready;
          await Promise.all(document.getAnimations().filter(animation => Number.isFinite(animation.effect.getComputedTiming().endTime)).map(animation => animation.finished.catch(() => {})));
        });
        const layout = await page.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
          return {overflow: document.documentElement.scrollWidth > innerWidth + 1,
            duplicateIds: ids.filter((id, index) => ids.indexOf(id) !== index)};
        });
        assert.equal(layout.overflow, false, `${name}: overflow at ${width}px`);
        assert.deepEqual(layout.duplicateIds, [], `${name}: duplicate IDs`);
        checks.push({page: name, width, theme});
        if ([1600, 390].includes(width)) {
          await page.screenshot({path: path.join(output, `${name}${theme ? '-' + theme : ''}-${width}.png`), animations: 'disabled'});
        }
      }
      await page.setViewportSize({width: 1600, height: 1000});
    };
    const fields = page => page.locator('.registration-editor [name]:not([type="hidden"])').evaluateAll(nodes =>
      nodes.map(node => ({name: node.name, type: node.type === 'tel' ? 'text' : node.type, required: node.required,
        options: node.options ? [...node.options].map(option => [option.value, option.text]) : null})));
    await publicPage.goto(process.env.QA_URL + process.env.QA_PUBLIC_ROUTE);
    await onsite.goto(process.env.QA_URL + process.env.QA_ONSITE_ROUTE);
    await onsite.locator('.onsite-record-status').waitFor();
    const publicFields = await fields(publicPage), onsiteFields = await fields(onsite);
    assert.equal(publicFields.find(field => field.name === 'pwd_number').required, true);
    assert.equal(onsiteFields.find(field => field.name === 'pwd_number').required, true);
    assert.deepEqual(onsiteFields, publicFields);
    assert.equal(await onsite.locator('[data-onsite-section]').count(), 7);
    assert.equal(await onsite.locator('.onsite-steps, [data-section-link], [data-onsite-progress]').count(), 0);
    for (const name of ['contact_number', 'spouse_contact', 'guardian_contact']) {
      assert.equal(await onsite.locator(`[name="${name}"]`).getAttribute('type'), 'tel');
    }
    assert.equal(await onsite.locator('.dashboard-public-link').getAttribute('href'), '/dashboard/');
    assert.equal(await publicPage.locator('[src*="onsite-registration"], [href*="onsite-registration.css"]').count(), 0);
    await responsive(publicPage, 'public-form');
    const noScript = await browser.newContext({javaScriptEnabled: false});
    await noScript.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL}]);
    const fallback = await noScript.newPage();
    await fallback.goto(process.env.QA_URL + process.env.QA_ONSITE_ROUTE);
    assert.equal(await fallback.locator('[data-save-registration]').isVisible(), true);
    assert.equal(await fallback.locator('[data-review-application]').isVisible(), false);
    assert.equal(await fallback.locator('[data-onsite-section]').count(), 7);
    await noScript.close();
    assert.equal(await onsite.locator('[data-save-draft], [data-restore-draft]').count(), 0);
    await onsite.locator('[name=first_name]').fill('Unsaved example');
    assert.equal(await onsite.locator('[data-record-status]').textContent(), 'Unsaved changes');
    assert.equal(await onsite.evaluate(() => JSON.stringify({...localStorage,...sessionStorage}).includes('Unsaved example')), false);
    await onsite.locator('[data-review-application]').click();
    assert.equal(await onsite.locator('[data-onsite-validation]').isVisible(), true);
    assert.equal(await onsite.locator('[data-onsite-review-dialog]').isVisible(), false);
    const data = JSON.parse(process.env.QA_FORM_DATA);
    for (const [name, value] of Object.entries(data)) {
      if (name === 'pwd_number') continue;
      const input = onsite.locator(`[name="${name}"]`);
      const tag = await input.evaluate(node => node.tagName);
      if (name === 'acknowledgement') await input.check();
      else if (tag === 'SELECT') await input.selectOption(value);
      else await input.fill(value);
    }
    assert.equal(await onsite.locator('#id_pwd_number').evaluate(node => node.validity.valueMissing), true);
    assert.equal(await onsite.locator('form.registration-editor').evaluate(node => node.checkValidity()), false);
    await onsite.locator('[data-review-application]').click();
    assert.equal(new URL(onsite.url()).pathname, process.env.QA_ONSITE_ROUTE);
    await onsite.locator('#id_pwd_number').fill(data.pwd_number);
    assert.equal(await onsite.locator('form.registration-editor').evaluate(node => node.checkValidity()), true);
    for (const theme of ['dark', 'light']) {
      if (await onsite.locator('html').getAttribute('data-dashboard-theme') !== theme) await onsite.locator('[data-dashboard-theme-toggle]').click();
      assert.equal(await onsite.evaluate(() => localStorage.getItem('santolan-dashboard-theme')), theme);
      await onsite.evaluate(() => scrollTo(0, 0));
      await responsive(onsite, 'onsite-form', theme);
      await onsite.locator('[data-review-application]').click();
      assert.equal(await onsite.locator('[data-onsite-review-dialog]').isVisible(), true);
      assert.match(await onsite.locator('[data-review-content]').textContent(), /Fictional/);
      assert.match(await onsite.locator('[data-review-content]').textContent(), /00-0000-000-0000001/);
      for (let index = 0; index < 6; index++) {
        await onsite.keyboard.press('Tab');
        assert.equal(await onsite.evaluate(() => Boolean(document.activeElement.closest('dialog'))), true);
      }
      await onsite.screenshot({path: path.join(output, `review-${theme}.png`)});
      await onsite.keyboard.press('Escape');
      assert.equal(await onsite.locator('[data-onsite-review-dialog]').isVisible(), false);
      assert.equal(await onsite.locator('[data-review-application]').evaluate(node => node === document.activeElement), true);
    }
    await onsite.setViewportSize({width: 390, height: 900});
    await onsite.locator('[data-review-application]').click();
    assert.equal(await onsite.locator('[data-onsite-review-dialog]').evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
    await onsite.locator('[data-close-review]').last().click();
    await onsite.evaluate(() => { document.documentElement.dataset.text = 'largest'; document.documentElement.dataset.contrast = 'true'; document.documentElement.dataset.motion = 'reduce'; });
    await onsite.emulateMedia({reducedMotion: 'reduce'});
    assert.equal(await onsite.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await onsite.evaluate(() => { delete document.documentElement.dataset.text; delete document.documentElement.dataset.contrast; delete document.documentElement.dataset.motion; });
    await onsite.emulateMedia({forcedColors: 'active'});
    assert.equal(await onsite.locator('[data-review-application]').isVisible(), true);
    await onsite.emulateMedia({forcedColors: 'none'});

    // Configured uploads are exercised on a rendered synthetic page. No files
    // or document-planning states are written to the operational application.
    const uploads = await adminContext.newPage();
    uploads.on('pageerror', error => errors.push(error.message));
    await uploads.route('**/synthetic-onsite-uploads/', route => route.fulfill({contentType: 'text/html',
      body: fs.readFileSync(path.join(output, 'configured-uploads.html'), 'utf8')}));
    await uploads.goto(process.env.QA_URL + '/synthetic-onsite-uploads/');
    const documentInput = uploads.locator('[name=civil_document]');
    assert.equal(await documentInput.count(), 1);
    await documentInput.setInputFiles({name: 'synthetic-proof.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nSynthetic evidence')});
    const uploadField = uploads.locator('[data-profile-field=civil_document]');
    assert.match(await uploadField.locator('[data-file-status]').textContent(), /synthetic-proof.pdf/);
    await uploadField.locator('[data-clear-upload]').click();
    assert.equal(await documentInput.evaluate(node => node.files.length), 0);
    assert.match(await uploadField.locator('[data-file-status]').textContent(), /No file selected/);
    await documentInput.setInputFiles({name: 'synthetic-proof.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nSynthetic evidence')});
    assert.equal(await documentInput.evaluate(node => node.files[0].name), 'synthetic-proof.pdf');
    await uploads.locator('[data-review-application]').click();
    assert.match(await uploads.locator('[data-onsite-validation]').textContent(), /Select Birth Certificate or Marriage Certificate/);
    await uploads.locator('[name=civil_alternative]').selectOption('birth');
    assert.equal(await uploads.locator('[name=civil_alternative]').evaluate(node => node.validity.valid), true);
    await uploadField.locator('[data-clear-upload]').click();
    assert.equal(await documentInput.evaluate(node => node.files.length), 0);
    await documentInput.setInputFiles({name: 'unsupported.txt', mimeType: 'text/plain', buffer: Buffer.from('Synthetic text')});
    await uploads.locator('[data-review-application]').click();
    assert.match(await uploads.locator('[data-onsite-validation]').textContent(), /file types/);
    await uploads.setViewportSize({width: 320, height: 900});
    assert.equal(await uploads.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await uploads.close();

    await onsite.setViewportSize({width: 1600, height: 1000});
    await onsite.locator('[data-review-application]').click();
    await Promise.all([
      onsite.waitForURL(/\/membership\/registrations\/AMR-[^/]+\/$/),
      onsite.locator('[data-confirm-registration]').click(),
    ]);
    assert.equal(await onsite.locator('#id_pwd_number').inputValue(), data.pwd_number);
    assert.equal(await onsite.locator('#id_first_name').inputValue(), data.first_name);
    assert.equal(await onsite.locator('#id_household_members').inputValue(), data.household_members);
    assert.equal(await onsite.locator('#id_pwd_number').getAttribute('required'), '');
    await responsive(onsite, 'onsite-review');
    const reference = new URL(onsite.url()).pathname.split('/').filter(Boolean).at(-1);
    await onsite.getByRole('button', {name: 'Approve membership', exact: true}).click();
    await onsite.waitForURL(/\/members\/\d+\/$/);
    await onsite.getByText('Registration approved. The applicant is now a member.', {exact: false}).first().waitFor();
    await responsive(onsite, 'onsite-approved');
    const savedRecord = onsite.url();
    await onsite.goto(process.env.QA_URL + '/admin/members/registration');
    assert.equal(new URL(onsite.url()).pathname, process.env.QA_ONSITE_ROUTE);
    await onsite.locator('#load-registration-reference').fill(reference);
    await Promise.all([onsite.waitForURL(savedRecord), onsite.locator('[data-lookup-button]').click()]);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({checks, errors,
      sharedApplicantFields: publicFields.length, requiredOnsitePwd: true,
      draft: 'removed', review: 'validation, modal, keyboard containment, Escape and mobile',
      uploads: 'configured controls, clear, reselect, invalid type',
      accessibility: 'large text, high contrast, reduced motion, forced colors',
      fallback: 'all fields and original submit work with JavaScript disabled',
      lookup: 'requested alias redirects to onsite; approved reference opens full member record',
      workflow: 'shared public and onsite fields; required PWD; retained intake; explicit approval'}, null, 2));
    console.log(`PASS: ${publicFields.length} shared fields; no draft controls; validation and review; both themes; configured uploads; saved intake and approval; ${checks.length} responsive checks.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
