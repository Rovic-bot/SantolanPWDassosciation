const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');

(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROME_EXECUTABLE ? {executablePath: process.env.CHROME_EXECUTABLE} : {})});
  try {
    const officer = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const visitor = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const page = await officer.newPage();
    const publicPage = await visitor.newPage();
    const errors = [];
    for (const current of [page, publicPage]) {
      current.on('pageerror', error => errors.push(error.message));
      current.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
      current.on('response', response => {if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`);});
    }
    const output = path.join(__dirname, '../.local/qa-confirmed-membership-20261010/browser');
    fs.mkdirSync(output, {recursive: true});
    const go = async (route, current = page) => {
      const response = await current.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200, route);
    };
    const screenshot = name => page.screenshot({path: path.join(output, name + '.png'), fullPage: true});
    const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Overflow at ${page.viewportSize().width}: ${page.url()}`);
    let responsiveChecks = 0;
    let enlargedTextChecks = 0;
    const responsive = async (current, name) => {
      for (const width of [320,390,768,1024,1440]) {
        await current.setViewportSize({width, height: 1000});
        assert.equal(await current.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `Overflow: ${name} at ${width}`);
        assert.deepEqual(await current.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(element => element.id);
          return ids.filter((id, index) => ids.indexOf(id) !== index);
        }), [], `Duplicate IDs: ${name}`);
        responsiveChecks += 1;
      }
      await current.screenshot({path: path.join(output, name + '-desktop.png'), fullPage: true});
      await current.setViewportSize({width: 390, height: 844});
      await current.locator('.display-trigger').click();
      await current.locator('#display-size').selectOption('largest');
      await current.locator('.display-close').click();
      assert.equal(await current.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `Largest text overflow: ${name}`);
      enlargedTextChecks += 1;
      await current.screenshot({path: path.join(output, name + '-mobile-largest.png'), fullPage: true});
      await current.locator('.display-trigger').click();
      await current.locator('#display-size').selectOption('default');
      await current.locator('.display-close').click();
      await current.setViewportSize({width: 1440, height: 1000});
    };
    await go('/membership/register/', publicPage);
    await publicPage.getByRole('heading', {name: 'How to become a member.', exact: true}).waitFor();
    const associationLabels = ['Membership Application Form', 'One (1) 2×2 ID Picture',
      'Birth Certificate OR Marriage Certificate', "Voter's Certificate", 'One (1) Long Envelope'];
    const checkAssociation = async current => assert.deepEqual(
      await current.locator('#association-requirements > li > strong').allTextContents(), associationLabels);
    await checkAssociation(publicPage);
    assert.equal(await publicPage.locator('#pdao-requirements > li').count(), 6);
    await publicPage.getByRole('heading', {name:'PDAO Renewal Only', exact:true}).waitFor();
    await publicPage.getByText('One (1) 1×1 ID Picture', {exact:true}).waitFor();
    assert.equal(await publicPage.getByText('Bring the original for onsite review.', {exact:true}).count(), 0);
    assert.equal(await publicPage.locator('main form, main input[type="file"]').count(), 0);
    assert.equal(await publicPage.getByText('Retired browser evidence', {exact: true}).count(), 0);
    assert.equal(await publicPage.getByText('Optional browser evidence', {exact:true}).count(), 0);
    await responsive(publicPage, 'guidelines');
    await publicPage.getByRole('button', {name:'Display preferences', exact:true}).focus();
    await publicPage.keyboard.press('Enter');
    assert.equal(await publicPage.locator('#display-size').evaluate(element => element === document.activeElement), true);
    await publicPage.getByLabel('High contrast', {exact:true}).check();
    assert.equal(await publicPage.locator('html').getAttribute('data-contrast'), 'true');
    await checkAssociation(publicPage);
    await publicPage.getByLabel('High contrast', {exact:true}).uncheck();
    await publicPage.keyboard.press('Escape');
    assert.equal(await publicPage.getByRole('button', {name:'Display preferences', exact:true}).evaluate(element => element === document.activeElement), true);
    if (await publicPage.evaluate(() => 'speechSynthesis' in window)) {
      await publicPage.getByRole('button', {name:'Display preferences', exact:true}).click();
      assert.equal(await publicPage.getByRole('button', {name:'Read page aloud', exact:true}).isVisible(), true);
      await publicPage.getByRole('button', {name:'Read page aloud', exact:true}).click();
      await publicPage.getByRole('button', {name:'Stop reading', exact:true}).click();
      await publicPage.getByRole('button', {name:'Close display preferences', exact:true}).click();
    }
    await go('/membership/submitted/', publicPage);
    assert.match(publicPage.url(), /membership\/register\/$/);
    await go('/membership/applications/new/', publicPage);
    assert.match(publicPage.url(), /accounts\/login\/\?next=/);
    await go('/accounts/login/');
    await page.getByLabel('Username:', {exact: true}).fill(process.env.QA_USERNAME);
    await page.getByLabel('Password:', {exact: true}).fill(process.env.QA_PASSWORD);
    await page.getByRole('button', {name: 'Sign in', exact: true}).click();
    await page.waitForURL('**/dashboard/');
    await page.locator('main').getByRole('link', {name: 'Onsite member registration', exact: true}).click();
    await page.waitForURL('**/membership/applications/new/');
    await checkAssociation(page);
    await responsive(page, 'onsite-encoding');
    const fillApplication = async (name, number) => {
      await go('/membership/applications/new/');
      await page.getByLabel('Full name').fill(name);
      await page.getByLabel('Birthdate').fill('1995-01-02');
      await page.getByLabel('Address', {exact: false}).fill('Synthetic test address, Santolan');
      await page.getByLabel('Contact number').fill('09170000000');
      await page.getByLabel('PWD control number').fill(number);
      await page.getByLabel('Disability information').fill('Synthetic browser test description');
      await page.locator('#id_disability_type').selectOption(process.env.QA_DISABILITY);
      await page.getByLabel('Employment information').fill('Synthetic browser test employment');
      await page.getByLabel('Monthly income').fill('1000');
      await page.getByLabel('Number of dependents').fill('2');
      await page.getByLabel('Test supporting document').setInputFiles({name:'test.pdf', mimeType:'application/pdf', buffer:Buffer.from('%PDF-1.4\nSynthetic test fixture\n%%EOF')});
      await page.getByRole('button', {name:'Save onsite registration for review'}).click();
      await page.waitForURL('**/membership/applications/*/');
      await page.getByRole('heading', {name, exact:true}).waitFor();
      await checkAssociation(page);
      await page.getByText('Pending', {exact:true}).waitFor();
      await noOverflow();
    };
    await fillApplication('Browser Approval Applicant', 'QA-MEMBER-001');
    await fillApplication('Browser Rejection Applicant', 'QA-MEMBER-002');
    await go('/membership/applications/');
    await noOverflow();
    await responsive(page, 'review-queue');
    await page.getByRole('link', {name:'Browser Approval Applicant', exact:true}).click();
    const detailUrl = page.url();
    await responsive(page, 'pending-review');
    assert.equal(await page.getByRole('link', {name:'Open PRPWD website', exact:false}).getAttribute('href'), 'https://registry.example.test/verify');
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', {name:'Download Test supporting document'}).click();
    const download = await downloadPromise;
    assert.match(download.suggestedFilename(), /^document-.*\.pdf$/);
    const decision = page.locator('form').filter({has: page.locator('input[name="action"][value="decide"]')});
    await decision.locator('select[name="decision"]').selectOption('approved');
    await decision.getByLabel('Decision notes').fill('Synthetic approval review');
    await decision.getByRole('button', {name:'Save membership decision'}).click();
    await page.getByText('Approval requires a recorded successful manual PRPWD verification.', {exact:true}).waitFor();
    await responsive(page, 'approval-blocked');
    const verification = page.locator('form').filter({has: page.locator('input[name="action"][value="verify"]')});
    await verification.getByLabel('PRPWD verification result').selectOption('yes');
    await verification.getByLabel('Verification notes').fill('Synthetic manual verification, no external lookup performed.');
    await verification.getByRole('button', {name:'Save verification'}).click();
    await page.getByRole('status').filter({hasText:'Verification saved.'}).waitFor();
    await decision.locator('select[name="decision"]').selectOption('approved');
    await decision.getByLabel('Decision notes').fill('Synthetic approval review');
    await decision.getByRole('button', {name:'Save membership decision'}).click();
    await page.getByText('An official member record has been created.', {exact:true}).waitFor();
    assert.equal(page.url(), detailUrl);
    await responsive(page, 'approved-review');
    await go('/membership/applications/');
    await page.getByRole('link', {name:'Browser Rejection Applicant', exact:true}).click();
    await page.locator('select[name="decision"]').selectOption('rejected');
    await page.getByLabel('Decision notes').fill('Synthetic rejection reason');
    await page.getByRole('button', {name:'Save membership decision'}).click();
    await page.getByRole('status').filter({hasText:'Membership decision saved.'}).waitFor();
    await responsive(page, 'rejected-review');
    await page.setViewportSize({width:390,height:844});
    await screenshot('rejected-mobile');
    await page.getByRole('button', {name:'Workspace menu'}).click();
    await page.getByRole('button', {name:'Sign out', exact:true}).click();
    await page.waitForURL('**/accounts/login/');
    await go('/membership/applications/');
    assert.match(page.url(), /accounts\/login\/\?next=/);
    assert.deepEqual(errors, []);
    const result = {status:'pass', actor:'ordinary authorized staff', widths:[320,390,768,1024,1440],
      responsiveChecks, enlargedTextChecks, browserErrors:errors,
      checks:['confirmed five-item Association guidance', 'separate six-item PDAO and renewal guidance',
        'private upload configuration retained', 'keyboard display controls and high contrast', 'TTS controls where supported',
        'public guidelines without online intake', 'retired receipt redirect', 'anonymous encoding denied',
        'onsite encoding with public intake closed', 'private download', 'approval blocked before verification',
        'manual verification', 'approval', 'rejection', 'duplicate IDs', 'logout protection', 'no resource/page errors'],
      screenshots:output};
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
