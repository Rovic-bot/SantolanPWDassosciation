const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs'), assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const origin = process.env.QA_URL, output = process.env.QA_OUTPUT, detail = process.env.QA_EVENT_DETAIL;
  try {
    const page = await browser.newPage({reducedMotion:'reduce'}), errors = [], mutations = [], layouts = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (request.method() !== 'GET') mutations.push(request.method()); });
    for (const theme of ['light','dark']) {
      for (const width of [1440,390,320]) {
        await page.setViewportSize({width,height:960});
        await page.goto(origin + '/');
        await page.evaluate(theme => document.documentElement.dataset.publicTheme = theme, theme);
        const card = page.locator('a.home-featured-event');
        assert.equal(await card.getAttribute('href'), '/events/');
        assert.equal(await card.locator('a').count(),0);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),true);
        await card.screenshot({path:`${output}/home-card-${theme}-${width}.png`});
        // The title itself, as well as the arrow, belongs to the same link.
        await card.locator('h2').click();
        await page.waitForURL(origin + '/events/');
        assert.equal(await page.locator('dialog[open]').count(),0);
        await page.evaluate(theme => document.documentElement.dataset.publicTheme = theme, theme);
        const opener = page.locator('[data-event-popup]').first();
        await opener.click();
        const dialog = page.locator('[data-public-dialog]');
        await dialog.locator('.event-poster-card').waitFor();
        assert.equal(page.url(),origin + '/events/');
        assert(await dialog.evaluate(el => {
          const r=el.getBoundingClientRect();
          return el.open && el.scrollWidth <= el.clientWidth + 1 && r.left >= 0 && r.right <= innerWidth;
        }));
        await dialog.screenshot({path:`${output}/event-popup-${theme}-${width}.png`});
        await page.keyboard.press('Escape');
        assert(await opener.evaluate(el => el === document.activeElement));
        layouts.push({theme,width,homeLink:true,popup:true,overflow:false});
      }
    }
    await page.goto(origin + '/');
    await page.locator('a.home-featured-event').focus();
    await page.keyboard.press('Enter');
    await page.waitForURL(origin + '/events/');
    let attempts = 0;
    await page.route('**/events/*/?popup=1', route => ++attempts === 1
      ? route.fulfill({status:503,body:'Unavailable'}) : route.continue());
    const opener = page.locator('[data-event-popup]').first();
    await opener.click();
    const dialog = page.locator('[data-public-dialog]');
    await dialog.getByRole('button',{name:'Try again',exact:true}).click();
    await dialog.locator('.event-poster-card').waitFor();
    assert.equal(attempts,2);
    assert.equal(page.url(),origin + '/events/');
    assert.equal(await dialog.getByText('Open the details page',{exact:true}).count(),0);
    await page.keyboard.press('Escape');
    assert(await opener.evaluate(el => el === document.activeElement));
    await page.goto(origin + detail);
    await page.waitForURL(origin + '/events/#scheduled-events');
    assert.equal(await page.locator('.event-poster-card').count(),0);
    const noJS = await browser.newContext({javaScriptEnabled:false});
    const fallback = await noJS.newPage();
    await fallback.goto(origin + '/');
    await fallback.locator('a.home-featured-event').click();
    await fallback.waitForURL(origin + '/events/');
    await fallback.goto(origin + detail);
    await fallback.waitForURL(origin + '/events/#scheduled-events');
    assert.deepEqual(errors,[]); assert.deepEqual(mutations,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({layouts,keyboard:true,retry:true,oldLinkRedirect:true,noJSNavigation:true,errors,mutations},null,2));
    console.log('Event navigation passed: Home card, 6 themed layouts, popups, retry, keyboard, old links, no-JavaScript navigation, no writes.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
