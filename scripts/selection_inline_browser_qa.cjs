const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 900}});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [], proof = [];
    let navigations = 0, posts = 0;
    page.on('pageerror', error => errors.push(error.message));
    page.on('framenavigated', frame => { if (frame === page.mainFrame()) navigations++; });
    page.on('request', request => { if (request.method() === 'POST') posts++; });
    const route = process.env.QA_URL + process.env.QA_ROUTE;
    assert.equal((await page.goto(route)).status(), 200);
    const applicant = await page.locator('#readiness').getAttribute('data-application');
    const other = await page.locator(`tr[data-applicant]:not([data-applicant="${applicant}"])`).getAttribute('data-applicant');
    const position = () => page.evaluate(() => ({x: scrollX, y: scrollY,
      panel: document.querySelector('#readiness').scrollTop,
      table: document.querySelector('#ranking-body .table-responsive').scrollLeft}));
    const feedback = page.locator('#readiness [data-selection-feedback]');

    async function action(name, next, {double = false, error = false} = {}) {
      const button = page.getByRole('button', {name, exact: true});
      await button.scrollIntoViewIfNeeded();
      const before = await position(), nav = navigations, beforePosts = posts, href = page.url();
      await page.evaluate(() => { window.inlineSelectionDocument = 'retained'; });
      await button.click();
      if (double) await page.locator('#readiness form').first().evaluate(form => form.requestSubmit());
      await page.waitForFunction(() => !document.querySelector('#readiness').hasAttribute('aria-busy'));
      if (!error && await feedback.innerText() !== 'Selection updated.') {
        console.error('Selection diagnostics:', {feedback: await feedback.innerText(), errors,
          state: await page.locator('#ranking-state').innerText()});
        await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'failure.png')});
      }
      if (error) assert.match(await feedback.innerText(), /changed|reload|Reload|confirm/i);
      else {
        await page.getByRole('button', {name: next, exact: true}).waitFor();
        assert.equal(await feedback.innerText(), 'Selection updated.');
        assert.equal((await page.evaluate(() => document.activeElement.textContent)).trim(), next,
          'Keyboard focus should follow the updated action without scrolling');
      }
      assert.equal(navigations, nav, 'Selection must not navigate or refresh the document');
      assert.equal(await page.evaluate(() => window.inlineSelectionDocument), 'retained');
      assert.equal(page.url(), href, 'Selection must not navigate to a page anchor');
      assert.equal(posts - beforePosts, 1, 'Only one POST per action');
      const after = await position();
      for (const key of Object.keys(before)) assert(Math.abs(before[key] - after[key]) <= 2,
        `${name}: ${key} moved from ${before[key]} to ${after[key]}`);
      proof.push({width: page.viewportSize().width, action: name, error, before, after, document_preserved: true});
    }

    // One write despite a second submit event while the request is pending.
    await action('Select for assistance', 'Unselect for assistance', {double: true});
    assert.match(await page.locator(`tr[data-applicant="${applicant}"] .ewaf-decision`).innerText(), /Selected/);
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'selected-desktop.png')});

    // Switching locally must use the updated cached selection controls.
    await page.locator(`tr[data-applicant="${other}"] [data-applicant-open]`).click();
    await page.locator(`tr[data-applicant="${applicant}"] [data-applicant-open]`).click();
    await page.getByRole('button', {name: 'Unselect for assistance', exact: true}).waitFor();
    await action('Unselect for assistance', 'Select for assistance');

    // The normal stale-revision validation stays visible, without a document reload.
    await page.locator('#readiness [name="decision-expected_revision"]').first().evaluate(input => { input.value = '99'; });
    await action('Select for assistance', '', {error: true});
    assert(await page.getByRole('button', {name: 'Select for assistance', exact: true}).isEnabled());

    // Search and decision filters survive a selection that removes its table row.
    const filtered = new URL(route);
    filtered.searchParams.set('q', process.env.QA_NAME);
    filtered.searchParams.set('decision', 'awaiting');
    await page.goto(filtered.href);
    await action('Select for assistance', 'Unselect for assistance');
    assert.equal(await page.locator('#ranking-filters [name=q]').inputValue(), process.env.QA_NAME);
    assert.equal(await page.locator('#ranking-filters [name=decision]').inputValue(), 'awaiting');
    assert.equal(await page.locator(`tr[data-applicant="${applicant}"]`).count(), 0);
    await action('Unselect for assistance', 'Select for assistance');
    assert.equal(await page.locator(`tr[data-applicant="${applicant}"]`).count(), 1);

    // On mobile the document scrolls instead of the sticky side panel.
    await page.goto(route);
    await page.setViewportSize({width: 390, height: 844});
    await action('Select for assistance', 'Unselect for assistance');
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'selected-mobile.png')});
    await action('Unselect for assistance', 'Select for assistance');

    // A failed request is never retried or converted into a full-page POST.
    const endpoint = new URL(route).pathname;
    await page.route(`**${endpoint}*`, async intercepted => {
      if (intercepted.request().method() === 'POST') await intercepted.abort('failed');
      else await intercepted.continue();
    });
    await action('Select for assistance', '', {error: true});
    await page.unroute(`**${endpoint}*`);
    await action('Select for assistance', 'Unselect for assistance');
    await page.reload();
    await page.getByRole('button', {name: 'Unselect for assistance', exact: true}).waitFor();
    assert.deepEqual(errors, []);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    fs.writeFileSync(path.join(process.env.QA_OUTPUT, 'browser-results.json'), JSON.stringify({checks: proof, errors}, null, 2));
    console.log('Inline selection/unselection, no navigation or scroll jump, duplicate submit, filters, cached panels, stale validation, failed network and persisted state passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
