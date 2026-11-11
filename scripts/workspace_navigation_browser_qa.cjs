const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT, routes = JSON.parse(process.env.QA_ROUTES);
  const errors = [], visited = [], requests = [];
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 800}, reducedMotion: 'reduce'});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: base}]);
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin ? route.continue() : route.abort());
    const page = await context.newPage();
    let documents = 0;
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      requests.push({url: request.url(), type: request.resourceType(), method: request.method()});
      if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents++;
    });
    await page.goto(base + routes['membership:encode']);
    await page.evaluate(() => {
      window.navigationTestDocument = 'retained';
      window.tabChanges = 0;
      document.addEventListener('workspace:navigated', () => window.tabChanges++);
    });
    const navigate = async (action, label) => {
      const before = await page.evaluate(() => ({count: window.tabChanges, y: scrollY}));
      await action();
      await page.waitForFunction(count => window.tabChanges > count, before.count);
      assert.equal(await page.evaluate(() => window.navigationTestDocument), 'retained', label);
      assert.equal(documents, 1, label + ': no document navigation');
      const position = await page.evaluate(() => ({y: scrollY, max: Math.max(0, document.documentElement.scrollHeight - innerHeight)}));
      assert.ok(Math.abs(position.y - Math.min(before.y, position.max)) <= 2, `${label}: scroll ${JSON.stringify({before, position})}`);
      assert.deepEqual(await page.evaluate(() => {
        const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
        return ids.filter((id, index) => ids.indexOf(id) !== index);
      }), [], label + ': unique IDs');
      visited.push(label);
    };
    const tab = async name => {
      const link = page.locator(`.workspace-module-links a[href="${routes[name]}"]`);
      await link.evaluate(node => { node.closest('details').open = true; });
      await navigate(() => link.click(), name);
      assert.equal(new URL(page.url()).pathname, routes[name]);
    };
    const verifyOnsite = async () => {
      for (const width of [1440, 900, 390]) {
        await page.setViewportSize({width, height: 800});
        const status = await page.locator('.onsite-record-status').boundingBox();
        const guide = await page.locator('.onsite-guide-card').boundingBox();
        assert.ok(status.y + status.height <= guide.y + 1);
        assert.ok(Math.abs(status.x - guide.x) <= 1 && Math.abs(status.width - guide.width) <= 1);
        assert.equal(await page.getByText('Upload does not replace required onsite presentation.', {exact: true}).count(), 0);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.screenshot({path: path.join(output, `onsite-${width}.png`)});
      }
      await page.setViewportSize({width: 1440, height: 800});
    };
    await verifyOnsite();
    await page.locator('[name=first_name]').fill('Unsaved synthetic draft');
    await page.evaluate(() => scrollTo({top: 350, behavior: 'instant'}));
    for (const name of ['member_directory', 'program_portfolio', 'event_workspace', 'application_workspace',
      'ewaf_selection', 'announcements:manage_list', 'core:content_list', 'assistance:referral_inbox',
      'assistance:release_programs', 'reports:members', 'core:dashboard', 'membership:review_home']) {
      await tab(name);
      const toggle = page.locator('[data-dashboard-theme-toggle]');
      const theme = await page.locator('html').getAttribute('data-dashboard-theme');
      await toggle.click();
      assert.notEqual(await page.locator('html').getAttribute('data-dashboard-theme'), theme, name + ': one theme listener');
    }
    await navigate(() => page.getByRole('link', {name: 'Review Association Membership', exact: true}).click(), 'Association reviews');
    assert.equal(await page.locator('.registration-inbox-heading, .registration-inbox-steps').count(), 0);
    assert.equal(await page.locator('main nav[aria-label="Membership reviews"]').count(), 0);
    await navigate(() => page.getByRole('link', {name: /^Completed/}).click(), 'Completed tab');
    assert.equal(new URL(page.url()).searchParams.get('tab'), 'completed');
    await navigate(() => page.getByRole('link', {name: /^All registrations/}).click(), 'All registrations tab');
    const beforeBack = await page.evaluate(() => window.tabChanges);
    await page.goBack();
    await page.waitForFunction(count => window.tabChanges > count, beforeBack);
    assert.equal(new URL(page.url()).searchParams.get('tab'), 'completed');
    const beforeForward = await page.evaluate(() => window.tabChanges);
    await page.goForward();
    await page.waitForFunction(count => window.tabChanges > count, beforeForward);
    assert.equal(new URL(page.url()).searchParams.get('tab'), 'all');
    await tab('membership:review_home');
    await navigate(() => page.getByRole('link', {name: 'Review PDAO Membership', exact: true}).click(), 'PDAO reviews');
    assert.equal(await page.locator('main nav').count(), 0);
    assert.equal(await page.getByText('Review, print and prepare applications for forwarding to PDAO. These records do not create Association members.', {exact: true}).count(), 0);
    const beforeSearch = requests.length;
    await navigate(() => page.locator('#pdao-search').fill('Synthetic'), 'PDAO search');
    assert.equal(await page.locator('#pdao-search').inputValue(), 'Synthetic');
    assert.equal(await page.locator('#pdao-search').evaluate(node => node === document.activeElement), true);
    assert.equal(requests.slice(beforeSearch).filter(item => new URL(item.url).pathname === routes['membership:pdao_inbox']).length, 1);
    for (let index = 0; index < 2; index++) {
      await tab('membership:encode');
      assert.equal(await page.locator('[name=first_name]').inputValue(), '');
      await tab('member_directory');
      await tab('core:dashboard');
    }
    // A failed GET preserves the current page, URL, and working controls.
    await page.route('**' + routes['membership:review_home'], route => route.abort());
    const currentUrl = page.url();
    const failedLink = page.locator(`.workspace-module-links a[href="${routes['membership:review_home']}"]`);
    await failedLink.evaluate(node => { node.closest('details').open = true; });
    await failedLink.click();
    await page.locator('.workspace-navigation-error').waitFor();
    assert.equal(page.url(), currentUrl);
    assert.equal(await page.locator('[data-dashboard-theme-toggle]').isVisible(), true);
    await page.unroute('**' + routes['membership:review_home']);
    await tab('membership:encode');
    await page.screenshot({path: path.join(output, 'onsite-after-switching.png')});
    assert.equal(documents, 1);
    assert.deepEqual(errors, []);
    assert.equal(requests.filter(item => item.method !== 'GET').length, 0);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({documents, errors, visited,
      checks: 'Scroll retention, tab history, repeated page lifecycle, search focus, failed GET recovery, private drafts cleared, responsive status placement'}, null, 2));
    console.log(`PASS: ${visited.length} tab/filter transitions, one browser document, responsive onsite layout, back/forward and failure recovery.`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
