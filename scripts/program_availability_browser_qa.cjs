const path = require('path'), fs = require('fs'), assert = require('assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || runtime);

(async () => {
  const fixtures = JSON.parse(process.env.QA_PROGRAMS);
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const output = path.join(__dirname, '../.local/qa-g07b');
  fs.mkdirSync(output, {recursive: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const go = async route => assert.equal((await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'})).status(), 200);
    const noOverflow = async label => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, label);
    const filters = page.getByRole('navigation', {name: 'Program period', exact: true});
    if (!Object.keys(fixtures).length) {
      await go('/programs/');
      assert.equal(await page.getByRole('heading', {name: 'There are no published programs to browse yet.'}).isVisible(), true);
      await filters.getByRole('link', {name: 'Available now', exact: true}).click();
      assert.equal(await page.getByRole('heading', {name: 'No programs match this category.'}).isVisible(), true);
      await page.getByRole('link', {name: 'Browse all programs', exact: true}).click();
      assert.equal(new URL(page.url()).searchParams.get('period'), 'all');
      assert.deepEqual(errors, []);
      console.log('G07-B empty catalog and category browser checks passed.');
      return;
    }
    const labels = {open: 'Applications open', upcoming: 'Upcoming application period', ended: 'Application period ended', cancelled: 'Cancelled program', unavailable: 'Applications unavailable'};
    await go('/programs/');
    assert.equal(await page.locator('.announcement-entry').count(), 10);
    assert.equal(await page.getByText('Synthetic hidden draft', {exact: true}).count(), 0);
    for (const label of Object.values(labels)) assert.ok(await page.locator('.quiet-badge').filter({hasText: label}).count());
    assert.equal(await filters.locator('[aria-current="page"]').innerText(), 'All programs');
    assert.equal(await page.locator('#public-nav .nav-link').count(), 7);
    for (const width of [320, 390, 768, 1024, 1440]) {
      await page.setViewportSize({width, height: 900});
      await noOverflow(`listing at ${width}`);
      if ([390, 1440].includes(width)) await page.screenshot({path: path.join(output, `list-${width}.png`), fullPage: true});
    }
    // The filters are ordinary keyboard-operable links; status is expressed as text.
    await filters.getByRole('link', {name: 'Available now', exact: true}).focus();
    await page.keyboard.press('Enter');
    await page.waitForURL('**/programs/?period=available');
    assert.equal(await page.locator('.announcement-entry').count(), 10);
    assert.deepEqual([...new Set(await page.locator('.announcement-entry .quiet-badge').allTextContents())], [labels.open]);
    await page.getByRole('link', {name: 'Next', exact: true}).click();
    assert.equal(new URL(page.url()).searchParams.get('period'), 'available');
    assert.equal(await page.locator('.announcement-entry').count(), 2);
    for (const [period, expected] of [['upcoming', [labels.upcoming]], ['past', [labels.ended]], ['unavailable', [labels.unavailable, labels.cancelled]]]) {
      await go(`/programs/?period=${period}`);
      assert.deepEqual((await page.locator('.announcement-entry .quiet-badge').allTextContents()).sort(), expected.sort());
      assert.equal(await filters.locator('[aria-current="page"]').count(), 1);
    }
    await go('/programs/?period=current');
    assert.equal(await page.getByText(labels.ended, {exact: true}).count(), 0);
    for (const [state, id] of Object.entries(fixtures)) {
      await go(`/programs/${id}/`);
      assert.equal(await page.getByText(labels[state], {exact: true}).isVisible(), true);
      assert.equal(await page.getByRole('link', {name: 'Apply for this program', exact: true}).count(), state === 'open' ? 1 : 0);
      if (state === 'upcoming') assert.ok((await page.locator('main').innerText()).includes('Scheduled opening:'));
      for (const width of [320, 390, 768, 1024, 1440]) {
        await page.setViewportSize({width, height: 900});
        await noOverflow(`${state} detail at ${width}`);
      }
      await page.screenshot({path: path.join(output, `detail-${state}.png`), fullPage: true});
    }
    for (const route of ['/programs/?period=upcoming', `/programs/${fixtures.upcoming}/`]) {
      await go(route);
      await page.setViewportSize({width: 320, height: 850});
      await page.evaluate(() => {document.documentElement.style.fontSize = '200%'; document.documentElement.dataset.contrast = 'true';});
      await noOverflow('Enlarged text and high contrast at 320px');
    }
    await page.screenshot({path: path.join(output, 'detail-enlarged-mobile.png'), fullPage: true});
    const noScript = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 850}});
    const plain = await noScript.newPage();
    await plain.goto(process.env.QA_URL + '/programs/?period=upcoming');
    assert.equal(await plain.getByText(labels.upcoming, {exact: true}).isVisible(), true);
    await plain.getByRole('link', {name: 'View Synthetic upcoming program', exact: true}).click();
    assert.equal(await plain.getByText(labels.upcoming, {exact: true}).isVisible(), true);
    assert.equal(await plain.getByRole('link', {name: 'Apply for this program', exact: true}).count(), 0);
    await noScript.close();
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({result: 'passed', lifecycleStates: 5, widths: [320,390,768,1024,1440], pagination: true, legacyBookmarks: true, keyboard: true, enlargedText: true, noScript: true, javascriptErrors: 0}));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exit(1);});
