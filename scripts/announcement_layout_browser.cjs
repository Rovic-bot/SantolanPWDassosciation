/* Synthetic GET responses and intercepted submissions: no application data is written. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const {scan} = require('./admin_palette_browser.cjs');
const base = 'http://127.0.0.1:8013';
const fixtures = path.resolve('.local/announcement-layout-synthetic');
const output = path.resolve(process.env.ANNOUNCEMENT_QA_OUTPUT || 'docs/announcement-composer-and-full-cards-2026-11-10');
const manifest = JSON.parse(fs.readFileSync(path.join(fixtures, 'manifest.json'), 'utf8'));
const key = value => { const u = new URL(value, base); if (u.searchParams.get('page') === '1') u.searchParams.delete('page'); u.searchParams.sort(); return u.pathname + u.search; };
const routes = new Map(manifest.map(row => [key(row.url), row.file]));
const createURL = manifest.find(row => row.url.endsWith('/new/')).url;
const manageURL = manifest.find(row => row.url.endsWith('/notices/')).url;
fs.mkdirSync(output, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
  const errors = [], checks = [], findings = [];
  let submission = 'errors', lastPost = '';
  const handleRoute = route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin === base && url.pathname === createURL && req.method() === 'POST') {
      lastPost = req.postData();
      if (submission === 'network') return route.abort();
      if (submission === 'success') return route.fulfill({contentType: 'application/json', body: JSON.stringify({redirect: manageURL})});
      return route.fulfill({contentType: 'text/html; charset=utf-8', body: fs.readFileSync(path.join(fixtures, 'errors.html'))});
    }
    if (req.method() !== 'GET') return route.abort();
    const file = routes.get(key(req.url()));
    if (url.origin === base && file) return route.fulfill({contentType: file.endsWith('.png') ? 'image/png' : file.endsWith('.jpg') ? 'image/jpeg' : 'text/html; charset=utf-8', body: fs.readFileSync(path.join(fixtures, file))});
    if (url.origin === base && url.pathname.startsWith('/static/')) return route.continue();
    if (url.hostname === 'cdn.tailwindcss.com') return route.fulfill({contentType: 'text/javascript', body: ''});
    return route.fulfill({status: 404, body: 'Outside the synthetic fixture'});
  };
  await context.route('**/*', handleRoute);
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  async function theme(name) {
    await page.evaluate(name => {
      document.documentElement.dataset.publicTheme = name === 'light' ? 'light' : 'dark';
      document.documentElement.dataset.dashboardTheme = name === 'light' ? 'light' : 'dark';
      document.documentElement.dataset.contrast = String(name === 'contrast');
    }, name);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  }
  async function inspect(name, mode, width) {
    const result = await scan(page);
    if (result.low.length) findings.push({name, mode, width, ...result});
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    checks.push({name, mode, width, overflow, checkedText: result.checked});
    assert(!overflow, name + ' page overflow');
  }
  const deck = page.locator('.notice-swipe-carousel');
  const visible = deck.locator('[data-swipe-card]:not([hidden])');
  async function waitPage(number) {
    await page.waitForFunction(number => document.querySelector('[data-swipe-status]')?.textContent.startsWith(`Card ${number} of`), number);
  }
  try {
    for (const mode of ['light', 'dark', 'contrast']) for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1000});
      await page.goto(base + '/announcements/');
      await theme(mode);
      await page.waitForSelector('.notice-swipe-carousel.is-ready');
      assert.equal(await visible.count(), width === 1440 ? 4 : 1);
      await visible.first().getByText('Read more', {exact: true}).click();
      await page.waitForSelector('[data-public-dialog][open] [data-public-popup-content]');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('[data-public-dialog][open]').count(), 0);
      await page.locator('.notice-topic-links').getByText('Announcements', {exact: true}).click();
      await waitPage(1);
      assert.equal(await visible.count(), 1);
      assert.equal(await deck.locator('[data-public-popup]').count(), 0);
      assert((await visible.innerText()).includes('Final announcement details.'));
      await inspect('announcement', mode, width);
      await deck.screenshot({path: path.join(output, `announcement-${mode}-${width}.png`)});
      const firstHeight = (await visible.boundingBox()).height;
      await deck.locator('[data-swipe-next]').click();
      await waitPage(2);
      assert((await visible.boundingBox()).height < firstHeight);
      assert.equal(await page.locator('.notice-full-initials').isVisible(), true);
      await page.locator('#announcement-cards').press('ArrowLeft');
      await waitPage(1);
      await page.locator('.notice-topic-links').getByText('Program Results', {exact: true}).click();
      await page.waitForURL('**/announcements/?category=results');
      await waitPage(1);
      assert.equal(await visible.count(), 1);
      assert.equal(await deck.locator('[data-public-popup]').count(), 0);
      assert((await visible.innerText()).includes('Final program details.'));
      assert((await visible.innerText()).includes('Selected members'));
      const artwork = visible.locator('.notice-full-artwork img');
      await artwork.evaluate(img => img.decode());
      assert((await artwork.getAttribute('src')).includes('/picture/'));
      assert.equal(await artwork.evaluate(img => getComputedStyle(img).objectFit), 'cover');
      assert((await visible.locator('.notice-full-artwork').evaluate(el => getComputedStyle(el, '::after').backgroundImage)).includes('linear-gradient'));
      const cardWidth = (await visible.boundingBox()).width;
      const heroWidth = (await visible.locator('.notice-full-hero').boundingBox()).width;
      assert(Math.abs(cardWidth - heroWidth) < 3, 'The picture header fills the card width');
      await visible.locator('.notice-full-jump').click();
      assert.equal(await page.evaluate(() => document.activeElement.className), 'notice-full-details');
      assert.equal(await page.locator('[data-public-dialog][open]').count(), 0);
      assert(await visible.locator('.notice-full-results').isVisible());
      await visible.locator('.notice-full-hero').screenshot({path: path.join(output, `results-header-${mode}-${width}.png`)});
      const viewport = await page.locator('[data-swipe-viewport]').boundingBox();
      assert(Math.abs(viewport.height - (await visible.boundingBox()).height) < 2);
      await inspect('results', mode, width);
      await deck.screenshot({path: path.join(output, `results-${mode}-${width}.png`)});
      const table = deck.locator('.table-responsive').first();
      const before = page.url();
      await table.press('ArrowRight');
      assert.equal(page.url(), before, 'Table navigation must not change result cards.');
      await deck.locator('[data-swipe-next]').click();
      await waitPage(2);
      assert.equal(await visible.locator('img[data-notice-image]').count(), 0);
      assert(await visible.locator('.notice-full-initials').isVisible());
      await page.locator('.notice-topic-links').getByText('All', {exact: true}).click();
      await page.waitForSelector('.notice-row');
      assert.equal(await visible.count(), width === 1440 ? 4 : 1);
      await page.goto(base + manageURL);
      await theme(mode);
      const opener = page.locator('[data-announcement-create]');
      await opener.click();
      const dialog = page.locator('[data-announcement-composer][open]');
      await dialog.locator('[name=title]').waitFor();
      assert.deepEqual(await dialog.locator('input:not([type=hidden]),textarea,select').evaluateAll(fields => fields.map(field => field.name)), ['title', 'content', 'image']);
      assert.equal(await page.evaluate(() => document.activeElement.name), 'title');
      await inspect('composer', mode, width);
      await dialog.screenshot({path: path.join(output, `composer-${mode}-${width}.png`)});
      for (let index = 0; index < 9; index++) {
        await page.keyboard.press('Tab');
        assert(await page.evaluate(() => !!document.activeElement.closest('[data-announcement-composer]')), 'Modal traps focus');
      }
      await page.keyboard.press('Escape');
      assert.equal(await dialog.count(), 0);
      assert(await opener.evaluate(el => el === document.activeElement));
    }
    // Mouse drag, touch swipe, browser history, no-JS fallback, and larger text.
    await page.goto(base + '/announcements/?category=announcements');
    await waitPage(1);
    await deck.scrollIntoViewIfNeeded();
    let box = await page.locator('.notice-full-artwork').boundingBox();
    await page.mouse.move(box.x + box.width * .85, box.y + 65);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * .15, box.y + 65, {steps: 12});
    await page.mouse.up();
    await waitPage(2);
    await page.goBack();
    await waitPage(1);
    await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
    await inspect('large-text', 'light', 390);
    await page.evaluate(() => {document.documentElement.style.fontSize = '';});
    const cdp = await context.newCDPSession(page);
    await deck.scrollIntoViewIfNeeded();
    box = await page.locator('.notice-full-artwork').boundingBox();
    const point = {x: box.x + box.width * .85, y: Math.max(30, box.y + 60)};
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [point]});
    for (let index = 1; index <= 8; index++) await cdp.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: point.x - index * 22, y: point.y}]});
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
    await waitPage(2);
    // Submission remains inside the popup on errors; original values survive network failure.
    await page.goto(base + createURL);
    let dialog = page.locator('[data-announcement-composer][open]');
    await dialog.locator('[name=title]').fill('Synthetic notice');
    await dialog.locator('[name=content]').fill('Synthetic content only.');
    await dialog.locator('[name=image]').setInputFiles(path.join(fixtures, 'image.png'));
    assert(await dialog.locator('[data-composer-preview]').isVisible());
    await dialog.locator('[data-composer-remove]').click();
    assert.equal(await dialog.locator('[name=image]').inputValue(), '');
    await dialog.locator('[type=submit]').click();
    await dialog.locator('[data-composer-errors]:not([hidden])').waitFor();
    assert.equal(await page.evaluate(() => document.activeElement.hasAttribute('data-composer-errors')), true);
    assert(!lastPost.includes('name="category"'));
    assert(!lastPost.includes('name="source_office"'));
    await dialog.locator('[name=title]').fill('Keep my title');
    await dialog.locator('[name=content]').fill('Keep my content');
    submission = 'network';
    await dialog.locator('[type=submit]').click();
    await dialog.getByText('The draft could not be saved.', {exact: false}).waitFor();
    assert.equal(await dialog.locator('[name=title]').inputValue(), 'Keep my title');
    submission = 'success';
    await dialog.locator('[type=submit]').click();
    await page.waitForURL(base + manageURL);
    await page.setViewportSize({width: 1440, height: 1000});
    // The editor must also initialize after the admin's partial-page navigation.
    await page.evaluate(() => { window.layoutNavigationCount = 0; document.addEventListener('workspace:navigated', () => window.layoutNavigationCount++); });
    await page.locator('.workspace-module-links a[href="/announcements/manage/"]').click();
    await page.waitForFunction(() => window.layoutNavigationCount === 1);
    await page.locator('[data-announcement-create]').click();
    await page.locator('[data-announcement-composer][open] [name=title]').waitFor();
    assert.equal(await page.locator('[data-announcement-composer]').count(), 1);
    await page.keyboard.press('Escape');
    await page.locator('.workspace-module-links a[href="/announcements/manage/"]').click();
    await page.waitForFunction(() => window.layoutNavigationCount === 2);
    await page.locator('[data-announcement-create]').click();
    await page.locator('[data-announcement-composer][open] [name=title]').waitFor();
    assert.equal(await page.locator('[data-announcement-composer]').count(), 1);
    await page.keyboard.press('Escape');
    await page.goto(base + '/announcements/?category=announcements&q=missing');
    assert.equal(await page.locator('[data-swipe-card]').count(), 0);
    assert((await page.locator('.notice-empty').innerText()).includes('No announcements match'));
    await page.setViewportSize({width: 390, height: 1000});
    await page.emulateMedia({forcedColors: 'active'});
    await page.goto(base + '/announcements/?category=results');
    await waitPage(1);
    await inspect('forced-colors', 'system', 390);
    await page.emulateMedia({forcedColors: 'none'});
    const noJSContext = await browser.newContext({javaScriptEnabled: false});
    await noJSContext.route('**/*', handleRoute);
    const noJS = await noJSContext.newPage();
    await noJS.goto(base + '/announcements/?category=announcements');
    assert.equal(await noJS.locator('.notice-full-card').count(), 1);
    assert(await noJS.locator('#announcement-pagination').isVisible());
    await noJS.goto(base + createURL);
    assert(await noJS.locator('[data-composer-page] [name=title]').isVisible());
    await noJSContext.close();
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({checks, findings, errors}, null, 2));
    assert.deepEqual(findings, [], 'Text contrast; see results.json');
    console.log(JSON.stringify({checks: checks.length, errors, findings: findings.length, interactions: 'passed'}));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
