const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1100}, colorScheme: 'dark'});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.QA_URL + process.env.QA_RECORD_ROUTE);
    await page.locator('.pdao-record').waitFor();
    assert.equal(await page.getByText('Other onsite applications', {exact: true}).count(), 0);
    for (const theme of ['dark', 'light']) {
      await page.evaluate(value => { localStorage.setItem('santolan-dashboard-theme', value); document.documentElement.dataset.dashboardTheme = value; }, theme);
      for (const width of [1600, 1024, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1100});
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `page overflow: ${theme} ${width}`);
        if ([1600, 390].includes(width)) await page.screenshot({path: path.join(process.env.QA_OUTPUT, `record-${theme}-${width}.png`)});
      }
    }
    await page.setViewportSize({width: 1600, height: 1100});
    await page.locator('.member-record-nav a[href="#pdao-details"]').click();
    const tabs = page.locator('#pdao-details [role=tab]');
    assert.equal(await tabs.count(), 8);
    await tabs.first().click();
    assert(await page.locator('#pdao-details #id_last_name').isVisible());
    assert.equal(await page.locator('#pdao-editor, #pdao-saved-history').count(), 0);
    for (let i = 1; i < await tabs.count(); i++) {
      await page.keyboard.press('ArrowRight');
      assert.equal(await tabs.nth(i).getAttribute('aria-selected'), 'true');
      assert.equal(await page.locator('#pdao-details [role=tabpanel]:visible').count(), 1);
    }
    await page.keyboard.press('Home');
    const profileHeight = (await page.locator('.member-record-profile-column').boundingBox()).height;
    assert.equal((await page.locator('.member-record-profile-column').boundingBox()).height, profileHeight);
    await page.locator('#id_first_name').fill('Reviewed');
    await page.getByRole('button', {name: 'Save reviewed details', exact: true}).click();
    await page.getByRole('heading', {name: 'Reviewed Example', exact: true}).waitFor();
    const reviewUrl = page.url();
    const printUrl = await page.locator('[data-pdao-preview-open]').getAttribute('href');
    for (const direct of [false, true]) {
      if (direct) await page.goto(process.env.QA_URL + printUrl);
      const before = page.url(), pages = context.pages().length;
      await page.locator('[data-pdao-preview-open]').click();
      const preview = page.frameLocator('[data-pdao-preview-frame]');
      await preview.locator('.pdao-sheet').first().waitFor();
      assert.equal(page.url(), before);
      assert.equal(context.pages().length, pages);
      assert.equal(await preview.locator('.pdao-sheet').count(), 2);
      assert(await preview.locator('body').textContent().then(text => text.includes('Reviewed Example')));
      await preview.locator('body').evaluate(() => { window.print = () => { window.previewPrinted = true; }; });
      await page.locator('[data-pdao-preview-print]').click();
      assert(await preview.locator('body').evaluate(() => window.previewPrinted));
      if (!direct) await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'pdao-print-preview.png')});
      await page.setViewportSize({width: 390, height: 844});
      assert(await preview.locator('body').evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      if (!direct) await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'pdao-print-preview-mobile.png')});
      await preview.locator('.pdao-preview').focus();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#pdao-preview-dialog').evaluate(el => el.open), false);
      await page.setViewportSize({width: 1600, height: 1100});
    }
    await page.goto(process.env.QA_URL + printUrl + '?preview=1');
    await page.setViewportSize({width: 390, height: 844});
    const pdf = await page.pdf({path: path.join(process.env.QA_OUTPUT, 'preview-print.pdf'), preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false});
    assert.equal((pdf.toString('latin1').match(/\/Type \/Page\b/g) || []).length, 2, 'Mobile preview must print as two full-size A4 pages.');
    await page.setViewportSize({width: 1600, height: 1100});
    await page.goto(reviewUrl);
    await page.getByRole('button', {name: 'Mark ready to forward', exact: true}).click();
    await page.locator('#pdao-forward-form input[name="confirmed"]').waitFor();
    assert.equal(await page.locator('.pdao-status').innerText(), 'Ready to forward');
    await page.locator('#pdao-forward-form input[name="confirmed"]').check();
    await page.getByRole('button', {name: 'Record forwarded to PDAO', exact: true}).click();
    await page.getByText('These details are now locked.', {exact: false}).waitFor();
    assert.equal(await page.locator('#pdao-review-form, #pdao-forward-form').count(), 0);
    assert.equal(await page.locator('.pdao-status').innerText(), 'Forwarded to PDAO');
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'record-forwarded.png')});
    await page.goto(process.env.QA_URL + process.env.QA_OLD_LIST);
    assert(new URL(page.url()).pathname.endsWith('/membership/reviews/'));
    assert.equal(await page.getByText('Other onsite applications', {exact: true}).count(), 0);
    await page.goto(process.env.QA_URL + process.env.QA_ONSITE_ROUTE);
    await page.locator('[data-onsite-form]').waitFor();
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `onsite overflow ${width}`);
      if (width !== 320) await page.screenshot({path: path.join(process.env.QA_OUTPUT, `onsite-${width}.png`)});
    }
    await page.setViewportSize({width: 1440, height: 1000});
    for (const [name, value] of Object.entries(JSON.parse(process.env.QA_ONSITE_DATA))) {
      const field = page.locator(`[name="${name}"]`);
      if (Array.isArray(value)) { for (const choice of value) await page.locator(`[name="${name}"][value="${choice}"]`).check(); }
      else if (await field.getAttribute('type') === 'checkbox') await field.check();
      else if (await field.evaluate(el => el.tagName) === 'SELECT') await field.selectOption(value);
      else await field.fill(value);
    }
    await page.locator('[data-review-application]').click();
    await page.locator('[data-onsite-review-dialog][open]').waitFor();
    assert.equal(await page.locator('[data-confirm-registration]').textContent(), 'Save PDAO application');
    await page.locator('[data-confirm-registration]').click();
    await page.getByRole('heading', {name: 'Onsite Example', exact: true}).waitFor();
    assert.equal(await page.locator('.pdao-status').textContent(), 'Received');
    assert(await page.getByText('Walk-in', {exact: true}).isVisible());
    const publicContext = await browser.newContext();
    const publicPage = await publicContext.newPage();
    publicPage.on('pageerror', error => errors.push(error.message));
    for (const width of [1440, 390, 320]) {
      await publicPage.setViewportSize({width, height: 1000});
      await publicPage.goto(process.env.QA_URL + process.env.QA_PUBLIC_ROUTE);
      assert(await publicPage.locator('body.membership-application-page').count());
      assert.equal(await publicPage.locator('.profile-section').count(), 8);
      assert.equal(await publicPage.locator('[name=disability_types]').count(), 10);
      assert(await publicPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `public overflow ${width}`);
      if (width !== 320) await publicPage.screenshot({path: path.join(process.env.QA_OUTPUT, `public-pdao-${width}.png`), fullPage: true});
    }
    await publicContext.close();
    assert.deepEqual(errors, []);
    const noJS = await browser.newContext({javaScriptEnabled: false});
    await noJS.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL}]);
    const fallback = await noJS.newPage();
    await fallback.goto(process.env.QA_URL + process.env.QA_RECORD_ROUTE);
    assert.equal(await fallback.locator('#pdao-details .member-registration-panel:visible').count(), 8);
    await noJS.close();
    console.log('Responsive public/onsite forms, inline editing, eight keyboard tabs, same-page print previews, onsite submission, retained originals, manual forwarding and forwarded locks passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
