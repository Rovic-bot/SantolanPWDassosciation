const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT;
  const manifest = JSON.parse(fs.readFileSync(path.join(output, 'manifest.json'), 'utf8'));
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], checks = [], writes = [];
  const cookie = {name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: base};
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    await context.addInitScript(() => {
      window.softFilterTransitions = 0;
      document.addEventListener('workspace:navigated', () => window.softFilterTransitions++);
    });
    await context.addCookies([cookie]);
    await context.route('**/*', route => {
      if (route.request().method() !== 'GET') { writes.push(route.request().method()); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    let documents = 0;
    page.on('request', request => { if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents++; });
    const navigate = async action => {
      if (await page.locator('[data-program-portfolio], [data-event-filters], [data-application-workspace]').count()) {
        const [response] = await Promise.all([
          page.waitForResponse(response => ['/admin/programs', '/admin/events', '/admin/applications'].includes(new URL(response.url()).pathname)), action()]);
        await page.waitForFunction(expected => {
          const actual=new URL(location.href), target=new URL(expected);
          return actual.pathname===target.pathname && [...target.searchParams].every(([key,value])=>actual.searchParams.get(key)===value) &&
            document.querySelector('[data-portfolio-results], [data-event-results], [data-review-results]')?.getAttribute('aria-busy') !== 'true';
        }, response.url());
        return;
      }
      if (!await page.locator('.native-admin-workspace').count()) {
        const count = await page.evaluate(() => window.softFilterTransitions);
        await action();
        await page.waitForFunction(previous => window.softFilterTransitions > previous, count);
        return;
      }
      await Promise.all([page.waitForNavigation({waitUntil: 'load'}), action()]);
      await page.waitForFunction(() => document.readyState === 'complete');
    };
    for (const entry of manifest.pages) {
      await page.goto(base + entry.url);
      const forms = page.locator('form[data-auto-filter-ready], form[data-portfolio-filters], form[data-event-filters], form[data-review-filters]');
      const portfolio = await page.locator('[data-program-portfolio], [data-event-filters], [data-application-workspace]').count() > 0;
      const count = await forms.count();
      for (let index = 0; index < count; index++) {
        let form = forms.nth(index);
        assert.equal(await form.locator('button[type=submit]:visible, button:not([type]):visible, input[type=submit]:visible').count(), 0, entry.name);
        const select = form.locator('select').first();
        if (await select.count()) {
          const option = await select.evaluate(node => [...node.options].find(option => option.value !== node.value && !option.disabled)?.value);
          const name = await select.getAttribute('name');
          if (option !== undefined) {
            const before = documents;
            await navigate(() => select.selectOption(option));
            assert.equal(new URL(page.url()).searchParams.get(name), option, `${entry.name}: ${name}`);
            assert.equal(documents - before, await page.locator('.native-admin-workspace').count() ? 1 : 0, `${entry.name}: filter navigation`);
            checks.push({page: entry.name, action: 'select', field: name});
          }
        }
        form = forms.nth(index);
        const search = form.locator('input:not([type]), input[type=search], input[type=text]').first();
        if (await search.count()) {
          const name = await search.getAttribute('name');
          await navigate(() => search.fill('Synthetic'));
          assert.equal(new URL(page.url()).searchParams.get(name), 'Synthetic', entry.name);
          assert.equal(await search.inputValue(), 'Synthetic');
          assert.equal(await search.evaluate(node => node === document.activeElement), true, entry.name + ': search focus');
          checks.push({page: entry.name, action: 'type', field: name});
        }
      }
    }

    // Checkbox changes apply immediately and preserve the other selected filters.
    await page.goto(base + '/programs/manage/?status=published&page=2');
    await page.locator('.portfolio-more-filters summary').click();
    await navigate(() => page.locator('[name=with_applications]').check());
    assert.equal(new URL(page.url()).searchParams.get('with_applications'), '1');
    assert.equal(new URL(page.url()).searchParams.get('status'), 'published');
    assert.equal(new URL(page.url()).searchParams.has('page'), false);
    checks.push({page: 'programs:manage_list', action: 'checkbox and pagination reset'});

    // Wait for both dates in a custom dashboard range; do not navigate on partial input.
    await page.goto(base + '/dashboard/');
    const beforeDates = documents;
    await page.locator('[name=period]').selectOption('custom');
    await page.waitForTimeout(500);
    assert.equal(documents, beforeDates);
    assert.equal(await page.locator('[name=start]').isVisible(), true);
    await page.locator('[name=start]').fill('2026-10-01');
    await page.waitForTimeout(500);
    assert.equal(documents, beforeDates);
    await navigate(() => page.locator('[name=end]').fill('2026-10-29'));
    assert.equal(new URL(page.url()).searchParams.get('end'), '2026-10-29');
    await navigate(() => page.locator('[name=program]').selectOption(manifest.program));
    assert.equal(new URL(page.url()).searchParams.get('start'), '2026-10-01');
    await navigate(() => page.locator('[name=period]').selectOption('year'));
    assert.equal(new URL(page.url()).searchParams.has('start'), false);
    assert.equal(await page.locator('[name=start]').isVisible(), false);
    checks.push({page: 'core:dashboard', action: 'complete custom dates, retained program, preset reset'});

    // Existing registration tab semantics: dropdown filtering retains the current tab.
    await page.goto(base + '/membership/registrations/?tab=completed');
    await navigate(() => page.locator('[name=channel]').selectOption('walk_in'));
    assert.equal(new URL(page.url()).searchParams.get('tab'), 'completed');
    checks.push({page: 'membership:registration_inbox', action: 'retained tab'});

    // IME composition does not navigate before a complete text input is committed.
    await page.goto(base + '/programs/manage/');
    const composingSearch = page.locator('[name=q]');
    const beforeComposition = documents;
    await composingSearch.dispatchEvent('compositionstart');
    await composingSearch.fill('Synthetic School');
    await page.waitForTimeout(550);
    assert.equal(documents, beforeComposition);
    await navigate(() => composingSearch.dispatchEvent('compositionend'));
    assert.equal(new URL(page.url()).searchParams.get('q'), 'Synthetic School');
    assert.equal(await page.evaluate(() => sessionStorage.getItem('santolan:filter-focus')), null);
    checks.push({page: 'programs:manage_list', action: 'composition and cleared focus metadata'});

    // Reset must cancel a pending search even if navigation takes longer than the debounce.
    await page.route('**/admin/programs?**', async route => {
      await new Promise(resolve => setTimeout(resolve, 650));
      await route.continue();
    });
    const beforeReset = documents;
    await page.locator('[name=q]').fill('Pending search to cancel');
    await navigate(() => page.locator('form [data-portfolio-reset]').click());
    assert.equal(new URL(page.url()).searchParams.get('q'), '');
    assert.equal(documents - beforeReset, 0);
    await page.unroute('**/admin/programs?**');
    checks.push({page: 'programs:manage_list', action: 'reset cancels pending search'});

    // POST editors and explicit reference-loading actions are not automatic filters.
    await page.goto(base + manifest.editor);
    const beforeEdit = documents;
    await page.locator('form[method=post] input[type=text]').first().fill('Unsubmitted edit');
    const editorSelect = page.locator('form[method=post] select').first();
    if (await editorSelect.count()) await editorSelect.selectOption({index: 0});
    await page.waitForTimeout(550);
    assert.equal(documents, beforeEdit);
    assert.equal(await page.locator('form[method=post][data-auto-filter-ready]').count(), 0);
    await page.goto(base + manifest.onsite);
    const lookup = page.locator('[data-onsite-lookup]');
    const beforeLookup = documents;
    await lookup.locator('[name=reference]').fill('AMR-000123');
    await page.waitForTimeout(550);
    assert.equal(documents, beforeLookup);
    assert.equal(await lookup.locator('button').isVisible(), true);
    await page.goto(base + '/programs/');
    assert.equal(await page.locator('script[src*="admin-filters.js"]').count(), 0);
    checks.push({action: 'POST editing, reference loading and public pages remain explicit'});

    // Layout and accessible focus remain usable across themes and viewport sizes.
    for (const url of ['/programs/manage/', '/membership/registrations/', '/assistance/referrals/inbox/', '/dashboard/']) {
      await page.goto(base + url);
      for (const theme of ['dark', 'light']) {
        if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
        for (const width of [1440, 390]) {
          await page.setViewportSize({width, height: 1000});
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `${url} ${theme} ${width}`);
        }
      }
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.goto(base + '/programs/manage/');
    await page.screenshot({path: path.join(output, 'automatic-program-filters.png')});

    // JavaScript-disabled clients retain a fully working native filter form.
    const plainContext = await browser.newContext({javaScriptEnabled: false});
    await plainContext.addCookies([cookie]);
    const plain = await plainContext.newPage();
    await plain.goto(base + '/programs/manage/');
    await plain.locator('[name=status]').selectOption('draft');
    await Promise.all([plain.waitForNavigation(), plain.getByRole('button', {name: 'Apply filters', exact: true}).click()]);
    assert.equal(new URL(plain.url()).searchParams.get('status'), 'draft');
    await plainContext.close();
    assert.deepEqual(writes, []);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({pages: manifest.pages.length, checks, errors, writes}, null, 2));
    console.log(`PASS: ${manifest.pages.length} admin pages, ${checks.length} automatic-filter workflows; no POST requests or JavaScript errors.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
