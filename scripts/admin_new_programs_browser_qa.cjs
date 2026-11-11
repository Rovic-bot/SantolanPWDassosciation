const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, url = base + process.env.QA_ROUTE, output = process.env.QA_OUTPUT;
  const cookie = {name:'sessionid', value:process.env.QA_ADMIN_SESSION, url:base};
  const errors = [], writes = [], checks = [];
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}, reducedMotion:'reduce'});
    await context.addCookies([cookie]);
    await context.route(base + '/**', route => {
      if (route.request().method() !== 'GET') { writes.push(route.request().method()); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url + '?status=published&sort=newest');
    await page.waitForFunction(() => document.querySelector('[data-portfolio-submit]')?.hidden);
    const marker = await page.evaluate(() => window.newFilterMarker = Math.random());
    const settled = (status, count) => page.waitForFunction(({status,count}) => {
      const results = document.querySelector('[data-portfolio-results]');
      return (new URL(location.href).searchParams.get('status') || '') === status &&
        results?.getAttribute('aria-busy') !== 'true' && Number(results?.dataset.resultCount) === count;
    }, {status,count});
    const firstTitle = () => page.locator('.portfolio-program h2').first().textContent();
    const sortLabel = () => page.locator('#program-sort option[value="newest"]').textContent();
    await page.locator('#program-status').selectOption('new');
    await settled('new',2);
    assert.match(await firstTitle(), /^Z recently/);
    assert.equal(await sortLabel(),'Newest published first');
    assert.equal(await page.evaluate(() => window.newFilterMarker),marker);
    assert.deepEqual(await page.locator('.portfolio-status').allTextContents(), ['Published','Published']);
    await page.locator('.portfolio-more-filters summary').click();
    await page.locator('#program-sort').selectOption('az');
    await page.waitForFunction(() => new URL(location.href).searchParams.get('sort') === 'az');
    assert.match(await firstTitle(), /^A earlier/);
    await page.locator('#program-status').selectOption('published');
    await settled('published',4);assert.equal(await sortLabel(),'Newest created first');
    await page.locator('#program-status').selectOption('new');await settled('new',2);
    await page.locator('#program-search').fill('No matching new program');await settled('new',0);
    assert(await page.getByRole('heading',{name:'No newly published programs found'}).isVisible());
    await page.locator('form [data-portfolio-reset]').click();await settled('',6);
    assert.equal(await sortLabel(),'Newest created first');
    for (const theme of ['light','dark','high-contrast']) for (const width of [1440,390]) {
      await page.setViewportSize({width,height:1000});
      await page.evaluate(theme => {
        localStorage.setItem('santolan-dashboard-theme',theme === 'light' ? 'light' : 'dark');
        localStorage.setItem('santolan-display',JSON.stringify({contrast:theme === 'high-contrast',motion:true}));
      },theme);
      await page.goto(url + '?status=new&sort=newest');
      await page.waitForFunction(() => document.querySelector('[data-portfolio-submit]')?.hidden);
      assert.equal(await page.locator('#program-status').inputValue(),'new');
      assert.equal(await sortLabel(),'Newest published first');
      assert.match(await firstTitle(), /^Z recently/);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.locator('[data-portfolio-filters]').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(output,`${theme}-${width}.png`)});
      checks.push({theme,width,newPrograms:2});
    }
    const plain = await browser.newContext({javaScriptEnabled:false});await plain.addCookies([cookie]);
    const nojs = await plain.newPage();await nojs.goto(url);
    await nojs.locator('#program-status').selectOption('new');
    await nojs.locator('[data-portfolio-submit]').click();
    await nojs.waitForURL(address => address.searchParams.get('status') === 'new');
    assert.equal(await nojs.locator('.portfolio-program').count(),2);
    assert.match(await nojs.locator('.portfolio-program h2').first().textContent(), /^Z recently/);
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({checks,inPlace:true,sorting:true,
      reset:true,emptyState:true,noJavaScript:true,errors,writes},null,2));
    console.log('Admin New filter passed: publication order, live sort labels, alternate sorting, search/reset, themes, mobile and no-JavaScript fallback.');
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
