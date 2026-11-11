const path = require('path'), fs = require('fs'), assert = require('assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || runtime);

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const output = path.join(__dirname, '../.local/observances-persistence-20261017/screenshots');
  fs.mkdirSync(output, {recursive: true});
  const errors = [];
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    const go = async route => {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200, route);
    };
    const layout = async (name, months = 12) => {
      for (const width of [320, 390, 768, 1024, 1440]) {
        await page.setViewportSize({width, height: 1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${name}: ${width}px overflow`);
        if (months) assert.equal(await page.locator('.observance-month').count(), months);
        if (width === 390 || width === 1440) {
          await page.screenshot({path: path.join(output, `${name}-${width}.png`), fullPage: true});
        }
      }
    };
    await go('/events/');
    assert.equal(await page.locator('.observance-card').count(), 0);
    await page.keyboard.press('Tab');
    assert.match(await page.locator(':focus').innerText(), /Skip to main content/);
    await page.keyboard.press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'main-content');
    await page.getByRole('link', {name: 'January', exact: true}).focus();
    assert.notEqual(await page.locator(':focus').evaluate(el => getComputedStyle(el).outlineStyle), 'none');
    await page.keyboard.press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'observance-month-1');
    await layout('public');
    assert.equal(await page.getByRole('link', {name: 'Past events', exact: true}).count(), 0);
    assert.equal(await page.getByRole('link', {name: 'Upcoming events', exact: true}).count(), 0);
    await page.locator('.display-trigger').click();
    await page.locator('#display-size').selectOption('largest');
    await page.locator('[data-preference="contrast"]').check();
    await page.locator('.display-close').click();
    await layout('public-large-contrast');
    await go('/accounts/login/');
    await page.locator('#id_username').fill(process.env.QA_USERNAME);
    await page.locator('#id_password').fill(process.env.QA_PASSWORD);
    await page.getByRole('button', {name: 'Sign in', exact: true}).click();
    await page.waitForLoadState('networkidle');
    await go('/events/manage/observances/');
    assert.equal(await page.locator('.workspace-module').count(), 8);
    assert.equal(await page.locator('.workspace-module a[aria-current="page"]').count(), 1);
    assert.equal(await page.locator('.workspace-module a[aria-current="page"]').innerText(), 'Events');
    assert.equal(await page.locator('.observance-card').count(), 11);
    assert.equal(await page.getByRole('link', {name: /Official source for/}).count(), 11);
    assert.equal(await page.locator('main form').count(), 0);
    assert.match(await page.locator('main').innerText(), /Verified annual references/);
    await layout('admin-large-contrast');
    await page.locator('.display-trigger').click();
    await page.locator('#display-size').selectOption('default');
    await page.locator('[data-preference="contrast"]').uncheck();
    await page.locator('.display-close').click();
    await layout('admin');
    await page.emulateMedia({forcedColors: 'active'});
    await layout('admin-forced-colors');
    await page.emulateMedia({forcedColors: 'none'});
    await page.getByRole('link', {name: 'Use this reference for National Autism Consciousness Week', exact: true}).click();
    assert.equal(await page.locator('#id_title').inputValue(), 'National Autism Consciousness Week');
    await page.locator('#id_title').fill('Fictional awareness photo card');
    await page.locator('#id_notes').fill('Fictional creation review');
    await page.locator('#id_image').setInputFiles(process.env.QA_PHOTO);
    await page.locator('#id_image_alt').fill('Fictional green awareness poster');
    await layout('admin-edit', 0);
    await page.getByRole('button', {name: 'Save draft', exact: true}).click();
    await page.waitForURL(/\/events\/manage\/observances\/[a-f0-9-]+\/$/);
    const detail = page.url().replace(process.env.QA_URL, '');
    assert.match(await page.locator('main').innerText(), /Draft/);
    await layout('admin-review', 0);
    const publish = async action => {
      await page.locator('#id_action').selectOption(action);
      await page.locator('#id_notes').fill('Fictional publication review');
      await page.locator('#id_confirm').check();
      await page.getByRole('button', {name: 'Apply publication change', exact: true}).click();
      await page.waitForLoadState('networkidle');
    };
    await go('/events/');
    assert.equal(await page.locator('.observance-card').count(), 0);
    await go(detail);
    await publish('published');
    await go('/events/');
    assert.equal(await page.locator('.observance-card').count(), 1);
    const photo = page.locator('.observance-photo');
    await photo.scrollIntoViewIfNeeded();
    await photo.evaluate(el => el.decode());
    assert.equal(await photo.getAttribute('alt'), 'Fictional green awareness poster');
    assert.equal(await photo.evaluate(el => Math.abs(el.clientWidth / el.clientHeight - el.naturalWidth / el.naturalHeight) < .02), true);
    assert.doesNotMatch(await page.locator('main').innerText(), /fictional_calendar_qa|Fictional publication review/);
    await layout('public-photo-grid');
    await page.setViewportSize({width: 1440, height: 1000});
    assert.equal(await page.locator('.observance-calendar').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length), 3);
    await page.setViewportSize({width: 768, height: 1000});
    assert.equal(await page.locator('.observance-calendar').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length), 2);
    await page.setViewportSize({width: 390, height: 1000});
    assert.equal(await page.locator('.observance-calendar').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length), 1);
    const oldPublicImage = await photo.getAttribute('src');
    await go(detail);
    await publish('draft');
    assert.equal((await context.request.get(process.env.QA_URL + oldPublicImage)).status(), 404);
    await page.getByRole('link', {name: 'Edit draft', exact: true}).click();
    await page.locator('#id_title').fill('Fictional revised awareness card');
    await page.locator('#id_notes').fill('Fictional photo replacement');
    await page.locator('#id_image').setInputFiles(process.env.QA_PHOTO);
    await page.locator('#id_image_alt').fill('Fictional replacement poster');
    await page.getByRole('button', {name: 'Save draft', exact: true}).click();
    await page.waitForLoadState('networkidle');
    await publish('published');
    await page.locator('section[aria-labelledby="revision-history"] summary').filter({hasText: /^Version 1 /}).click();
    assert.equal(await page.getByRole('link', {name: 'View photo from version 1', exact: true}).count(), 1);
    await layout('admin-history', 0);
    await go('/events/');
    assert.match(await page.locator('.observance-card').innerText(), /Fictional revised awareness card/);
    await layout('public-revised-photo-grid');
    const noScript = await browser.newContext({javaScriptEnabled: false, storageState: await context.storageState(), viewport: {width: 320, height: 900}});
    const plain = await noScript.newPage();
    for (const route of ['/events/', '/events/manage/observances/']) {
      await plain.goto(process.env.QA_URL + route);
      assert.equal(await plain.locator('.observance-month').count(), 12);
      assert.equal(await plain.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    }
    await noScript.close();
    assert.deepEqual(errors, []);
    console.log('PASS: create from reference, photo upload, private draft, publish, withdraw, replace photo, republish and history; public 3/2/1-column grid; 320/390/768/1024/1440px; keyboard; large text/high contrast; forced colors; no JavaScript; eight groups; zero JS errors.');
    console.log('Screenshots:', output);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
