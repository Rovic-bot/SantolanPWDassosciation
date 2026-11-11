const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROME_EXECUTABLE ? {executablePath: process.env.CHROME_EXECUTABLE} : {})});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    const output = path.join(__dirname, '../docs/phase2a-reference-retrieval-2026-10-23/ui');
    fs.mkdirSync(output, {recursive: true});
    const go = async route => {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
    };
    const layoutChecks = [];
    const responsive = async name => {
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({width, height: 1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${name}: overflow at ${width}`);
        const duplicateIds = await page.evaluate(() => {
          const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
          return ids.filter((id, i) => ids.indexOf(id) !== i);
        });
        assert.deepEqual(duplicateIds, [], `${name}: duplicate IDs`);
        layoutChecks.push({name, width});
      }
    };
    await go('/accounts/login/');
    await page.getByLabel('Username:', {exact:true}).fill(process.env.QA_USERNAME);
    await page.getByLabel('Password:', {exact:true}).fill(process.env.QA_PASSWORD);
    await page.getByRole('button', {name:'Sign in', exact:true}).click();
    await page.waitForURL('**/dashboard/');
    await go(process.env.QA_LIST);
    assert.equal(await page.getByText('Synthetic Rejected Applicant', {exact:true}).count(), 0);
    await responsive('pending-list');
    const input = page.getByRole('searchbox', {name:'Application reference', exact:true});
    await input.focus();
    await page.keyboard.type(process.env.QA_REFERENCE);
    await page.keyboard.press('Tab');
    assert.equal(await page.getByRole('button', {name:'Find reference', exact:true}).evaluate(e => e === document.activeElement), true);
    await page.keyboard.press('Enter');
    await page.waitForURL('**/?reference=*');
    await page.getByRole('status').filter({hasText:'Reference lookup: 1 matching record.'}).waitFor();
    assert.equal(await page.getByText('Synthetic Pending Applicant', {exact:true}).count(), 0);
    await responsive('reference-result');
    await page.screenshot({path:path.join(output, 'reference-result-desktop.png'), fullPage:true});
    await page.setViewportSize({width:390, height:1000});
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, '200% text overflow');
    await page.screenshot({path:path.join(output, 'reference-result-mobile-200percent.png'), fullPage:true});
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
    await page.getByRole('link', {name:process.env.QA_REFERENCE, exact:true}).focus();
    await page.keyboard.press('Enter');
    await page.waitForURL('**' + process.env.QA_DETAIL);
    await page.getByRole('heading', {name:'Synthetic Rejected Applicant', exact:true}).waitFor();
    await responsive('existing-detail');
    await go(process.env.QA_LIST + '?reference=not-a-reference');
    await page.getByRole('alert').filter({hasText:'Enter the complete application reference'}).waitFor();
    assert.equal(await input.getAttribute('aria-invalid'), 'true');
    assert.match(await input.getAttribute('aria-describedby'), /reference-error/);
    await responsive('invalid-reference');
    await page.getByRole('link', {name:'Return to pending applications', exact:true}).click();
    await page.getByText('Synthetic Pending Applicant', {exact:true}).waitFor();
    const publicContext = await browser.newContext();
    const visitor = await publicContext.newPage();
    await visitor.goto(process.env.QA_URL + process.env.QA_LIST + '?reference=' + process.env.QA_REFERENCE);
    assert.match(visitor.url(), /accounts\/login\//);
    assert.equal(await visitor.getByText('Synthetic Rejected Applicant', {exact:true}).count(), 0);
    assert.deepEqual(errors, []);
    const result = {browser:await browser.version(), responsiveChecks:layoutChecks,
      keyboardLookupAndDetail:true, invalidReferenceSemantics:true,
      mobile200PercentText:true, anonymousRedirect:true, pageAndConsoleErrors:errors,
      limitations:['No screen-reader session, contrast measurement, WCAG certification or representative-user UAT.']};
    fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify(result,null,2) + '\n');
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
