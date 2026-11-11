const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.CHROME_EXECUTABLE ? {executablePath:process.env.CHROME_EXECUTABLE} : {})});
  const output = path.join(__dirname, '../docs/phase2b-association-foundation-2026-10-23/ui');
  fs.mkdirSync(output, {recursive:true});
  const checks = [];
  const errors = [];
  const expectedErrors = [];
  const watch = page => {
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
      if (message.type() !== 'error') return;
      (/status of 400/.test(message.text()) ? expectedErrors : errors).push(message.text());
    });
  };
  const go = async (page, route) => {
    const response = await page.goto(process.env.QA_URL + route, {waitUntil:'networkidle'});
    assert.equal(response.status(), 200, route);
  };
  const responsive = async (page, name) => {
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({width,height:1000});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${name}: overflow ${width}`);
      const duplicateIds = await page.evaluate(() => {
        const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
        return ids.filter((id,index) => ids.indexOf(id) !== index);
      });
      assert.deepEqual(duplicateIds, [], `${name}: duplicate IDs`);
      checks.push({name,width});
    }
  };
  try {
    const applicant = await browser.newContext();
    const page = await applicant.newPage();
    watch(page);
    await go(page, '/membership/registration/apply/');
    await responsive(page, 'public-form');
    assert.equal(await page.getByLabel(/long envelope/i).count(), 0);
    await page.screenshot({path:path.join(output, 'public-form-desktop.png'), fullPage:true});
    await page.locator('form[method="post"]').evaluate(form => { form.noValidate = true; });
    await page.getByRole('button', {name:'Submit pending registration', exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Please review the following'}).waitFor();
    assert.equal(await page.getByLabel('Applicant full name:', {exact:true}).getAttribute('aria-invalid'), 'true');
    await responsive(page, 'validation-errors');
    await page.getByLabel('Applicant full name:', {exact:true}).fill('Synthetic Association Applicant');
    await page.getByLabel('Date of birth:', {exact:true}).fill('1992-07-15');
    await page.getByLabel('Residence address:', {exact:true}).fill('Synthetic residence, no real household');
    await page.getByLabel('I have read the privacy notice and reviewed my submitted information.', {exact:true}).check();
    await page.getByLabel("Voter's Certificate (optional pre-upload):", {exact:true}).setInputFiles({
      name:'synthetic-certificate.pdf', mimeType:'application/pdf', buffer:Buffer.from('%PDF-1.4\nSynthetic test document only\n')});
    await page.getByRole('button', {name:'Submit pending registration', exact:true}).focus();
    await page.keyboard.press('Enter');
    await page.waitForURL('**/membership/registration/receipt/');
    const reference = (await page.locator('.registration-reference strong').innerText()).trim();
    assert.match(reference, /^AMR-/);
    await responsive(page, 'submitted-form-receipt');
    await page.screenshot({path:path.join(output, 'receipt-desktop.png'), fullPage:true});
    await page.setViewportSize({width:390,height:1000});
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; window.print = () => { window.syntheticPrintCalls = (window.syntheticPrintCalls || 0) + 1; }; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, 'receipt: 200% overflow');
    await page.screenshot({path:path.join(output, 'receipt-mobile-200percent.png'), fullPage:true});
    await page.getByRole('button', {name:'Print or save submitted form', exact:true}).click();
    assert.equal(await page.evaluate(() => window.syntheticPrintCalls), 1);
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('.registration-controls').isVisible(), false);
    await page.emulateMedia({media:'screen'});

    const staffContext = await browser.newContext();
    const review = await staffContext.newPage();
    watch(review);
    await go(review, '/accounts/login/');
    await review.getByLabel('Username:', {exact:true}).fill(process.env.QA_USERNAME);
    await review.getByLabel('Password:', {exact:true}).fill(process.env.QA_PASSWORD);
    await review.getByRole('button', {name:'Sign in', exact:true}).click();
    await review.waitForURL('**/dashboard/');
    await go(review, '/membership/applications/');
    await review.getByRole('link', {name:'Pending Association registrations', exact:true}).click();
    await review.waitForURL('**/membership/registrations/');
    const search = review.getByRole('searchbox', {name:'Registration reference', exact:true});
    await search.focus();
    await review.keyboard.type(reference);
    await review.keyboard.press('Tab');
    assert.equal(await review.getByRole('button', {name:'Find reference', exact:true}).evaluate(node => node === document.activeElement), true);
    await review.keyboard.press('Enter');
    await review.waitForURL('**/membership/registrations/?reference=*');
    await responsive(review, 'staff-reference-inbox');
    await review.screenshot({path:path.join(output, 'staff-inbox-desktop.png'), fullPage:true});
    await review.getByRole('link', {name:reference, exact:true}).focus();
    await review.keyboard.press('Enter');
    await review.waitForURL('**/membership/registrations/' + reference + '/');
    await responsive(review, 'staff-detail');
    const documentUrl = await review.getByRole('link', {name:'voter_certificate', exact:true}).first().getAttribute('href');
    const file = await staffContext.request.get(process.env.QA_URL + documentUrl);
    assert.equal(file.status(), 200);
    assert.match(file.headers()['content-disposition'], /attachment/);
    assert.match(await file.text(), /^%PDF-/);
    await review.getByLabel('Action:', {exact:true}).selectOption('begin_review');
    await review.getByLabel('Reason / private review note:', {exact:true}).fill('PRIVATE synthetic reviewer note');
    await review.getByRole('button', {name:'Save review', exact:true}).click();
    await review.getByRole('status').filter({hasText:'Review saved'}).waitFor();
    await review.getByRole('link', {name:'Record onsite observations', exact:true}).click();
    await responsive(review, 'onsite-observations');
    for (const key of ['form','photo','civil','voter','envelope']) await review.locator('#id_finding_' + key).selectOption('sighted');
    await review.getByLabel('Civil document presented:', {exact:true}).selectOption('birth');
    await review.getByLabel('Private onsite findings:', {exact:true}).fill('Synthetic observation only; no official approval.');
    await review.getByRole('button', {name:'Save onsite observations', exact:true}).click();
    await review.getByRole('status').filter({hasText:'Onsite observations retained'}).waitFor();
    await review.getByRole('link', {name:'Record a correction', exact:true}).click();
    await responsive(review, 'assisted-correction');
    await review.getByLabel('Correction reason (required)', {exact:true}).fill('PRIVATE synthetic correction reason');
    await review.getByLabel('Applicant full name:', {exact:true}).fill('Synthetic Corrected Applicant');
    await review.getByRole('button', {name:'Save pending information', exact:true}).click();
    await review.getByRole('status').filter({hasText:'Correction retained'}).waitFor();
    await review.screenshot({path:path.join(output, 'staff-review-history.png'), fullPage:true});
    await review.getByRole('link', {name:'View / print submitted form', exact:true}).click();
    await responsive(review, 'staff-completed-form');
    assert.equal(await review.getByText('PRIVATE synthetic correction reason', {exact:true}).count(), 0);
    await page.reload({waitUntil:'networkidle'});
    assert.equal(await page.getByText('Synthetic Association Applicant', {exact:true}).count(), 1);
    assert.equal(await page.getByText('Synthetic Corrected Applicant', {exact:true}).count(), 0);

    const outsider = await browser.newContext();
    for (const route of ['/membership/registrations/' + reference + '/', documentUrl]) {
      const denied = await outsider.request.get(process.env.QA_URL + route, {maxRedirects:0});
      assert.equal(denied.status(), 302);
      assert.match(denied.headers().location, /accounts\/login/);
    }
    assert.equal((await outsider.request.get(process.env.QA_URL + '/membership/registration/receipt/?reference=' + reference)).status(), 403);
    for (const route of ['pdao','tracking','recovery','handoff']) {
      assert.equal((await outsider.request.get(process.env.QA_URL + '/membership/registration/' + route + '/')).status(), 404);
    }
    await page.getByRole('button', {name:'Done — show my reference number', exact:true}).click();
    await page.getByRole('heading', {name:'Registration submitted', exact:true}).waitFor();
    assert.equal((await applicant.request.get(process.env.QA_URL + '/membership/registration/receipt/')).status(), 403);
    assert.deepEqual(errors, []);
    const evidence = {captured_utc:new Date().toISOString(), browser:browser.version(),
      policy:'SYNTHETIC TEST PARAMETERS ONLY; no institutional approval or real-data activation',
      checks, keyboard_submission_and_reference_lookup:true, enlarged_receipt_text:true,
      print_control_and_print_css:true, receipt_original_revision:true, private_document_authorization:true,
      shared_device_finish_revoked:true, official_member_creation:false, console_errors:errors,
      expected_validation_console_messages:expectedErrors,
      limitations:['No representative screen-reader session, measured contrast audit, UAT or WCAG certification.']};
    fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify(evidence,null,2));
    process.stdout.write(JSON.stringify({responsive_checks:checks.length, browser:evidence.browser, errors:errors.length}) + '\n');
    await applicant.close(); await staffContext.close(); await outsider.close();
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
