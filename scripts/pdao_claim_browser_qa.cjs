const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const origin = process.env.QA_URL, data = JSON.parse(process.env.QA_DATA), output = process.env.QA_OUTPUT;
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], layouts = [];
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: origin}]);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    const count = async n => page.waitForFunction(n => document.querySelector('[data-directory-count]')?.textContent.trim() === String(n), n);
    await page.goto(origin + '/admin/members');
    await page.locator('#directory-disability').selectOption(data.hearing);
    await count(2);
    await page.locator('#directory-search').fill('Shared');
    await count(1);
    await page.locator('#directory-search').fill('');
    await count(2);
    await page.locator('#directory-disability').selectOption(data.visual);
    await count(22);
    await page.locator('[data-directory-page]').filter({hasText: 'Next'}).click();
    await page.waitForFunction(() => new URL(location.href).searchParams.get('page') === '2');
    assert.equal(new URL(page.url()).searchParams.get('disability'), data.visual);
    assert.equal(await page.locator('[data-select-member]').count(), 2);
    await page.goBack();
    await page.waitForFunction(() => !new URL(location.href).searchParams.has('page'));
    assert.equal(await page.locator('#directory-disability').inputValue(), data.visual);
    await page.locator('[data-clear-directory-filters]').first().click();
    await count(23);
    assert.equal(await page.locator('#directory-disability').inputValue(), '');
    for (const theme of ['light', 'dark']) {
      await page.evaluate(theme => document.dispatchEvent(new CustomEvent('santolan:setadmintheme', {detail: theme})), theme);
      for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Directory ${theme} ${width}`);
        if ([1440, 390].includes(width)) await page.locator('.directory-toolbar').screenshot({path: path.join(output, `directory-${theme}-${width}.png`)});
        layouts.push({page: 'directory', theme, width});
      }
    }
    const plain = await browser.newContext({javaScriptEnabled: false});
    await plain.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: origin}]);
    const fallback = await plain.newPage();
    await fallback.goto(origin + '/admin/members');
    await fallback.locator('#directory-disability').selectOption(data.hearing);
    await fallback.getByRole('button', {name: 'Filter records', exact: true}).click();
    assert.equal((await fallback.locator('[data-directory-count]').innerText()).trim(), '2');
    await plain.close();

    await page.goto(origin + '/membership/reviews/pdao/?state=forwarded');
    for (const theme of ['light', 'dark']) {
      await page.evaluate(theme => document.dispatchEvent(new CustomEvent('santolan:setadmintheme', {detail: theme})), theme);
      for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Forwarded ${theme} ${width}`);
        if ([1440, 390].includes(width)) await page.locator('.pdao-claim-toolbar').screenshot({path: path.join(output, `claim-toolbar-${theme}-${width}.png`)});
        layouts.push({page: 'forwarded', theme, width});
      }
    }
    await page.setViewportSize({width: 1440, height: 1000});
    const submit = page.locator('[data-claim-submit]');
    assert.ok(await submit.isDisabled());
    assert.ok(await page.locator(`[data-claim-select][value^="${data.missing}:"]`).isDisabled());
    await page.locator('[data-claim-all]').check();
    assert.match(await page.locator('[data-claim-count]').innerText(), /^3 selected/);
    await page.locator(`[data-claim-select][value^="${data.untouched}:"]`).uncheck();
    assert.match(await page.locator('[data-claim-count]').innerText(), /^2 selected/);
    assert.ok(await submit.isDisabled());
    await page.locator('#pdao-claim-form input[name=confirmed]').check();
    assert.ok(await submit.isEnabled());
    await page.locator('.registration-inbox-results').screenshot({path: path.join(output, 'selected-applicants.png')});
    await submit.click();
    await page.waitForLoadState('networkidle');
    for (let attempt = 0; attempt < 10 && await page.locator('.pdao-claim-delivery [data-state=sent]').count() !== 2; attempt++) {
      await page.getByRole('link', {name: 'Refresh email status', exact: true}).click();
      await page.waitForLoadState('networkidle');
    }
    assert.equal(await page.locator('.pdao-claim-delivery [data-state=sent]').count(), 2);
    assert.equal(await page.locator('[data-claim-select]:not(:disabled)').count(), 1);
    await page.locator('.registration-inbox-results').screenshot({path: path.join(output, 'delivered-claims.png')});

    await page.goto(origin + data.single);
    assert.equal(await page.getByRole('button', {name: 'Send PWD ID claim email', exact: true}).count(), 0);
    await page.locator('#pdao-forward-form input[name=confirmed]').check();
    await page.getByRole('button', {name: 'Record forwarded to PDAO', exact: true}).click();
    const singleButton = page.getByRole('button', {name: 'Send PWD ID claim email', exact: true});
    await singleButton.waitFor();
    await page.locator('.pdao-claim-action input[name=confirmed]').check();
    await page.locator('.pdao-claim-action').evaluate(element => element.scrollIntoView({block: 'center'}));
    await page.locator('.pdao-claim-action').screenshot({path: path.join(output, 'single-claim-action.png')});
    await singleButton.click();
    await page.waitForLoadState('networkidle');
    for (let attempt = 0; attempt < 10 && !/Saved to test outbox/.test(await page.locator('.pdao-email-status').innerText()); attempt++) {
      await page.reload();
    }
    assert.match(await page.locator('.pdao-email-status').innerText(), /PWD ID ready for collection/);
    assert.match(await page.locator('.pdao-email-status').innerText(), /Saved to test outbox/);
    assert.equal(await singleButton.count(), 0);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({layouts, errors, filtering: true, pagination: true,
      noJavaScriptFilter: true, bulkClaim: true, singleAfterForwarding: true}, null, 2));
    console.log('PASS: directory filters/pagination, 16 responsive layouts, bulk selection and single claim email after forwarding.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
