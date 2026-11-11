const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.addCookies([{name:'sessionid',value:process.env.QA_SESSION,url:process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    assert.equal((await page.goto(process.env.QA_URL + process.env.QA_ROUTE)).status(), 200);
    assert.match(await page.locator('main').innerText(), /Registration is open/);
    const select = page.getByRole('button',{name:'Select for assistance',exact:true});
    assert(await select.isEnabled());
    await select.scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.QA_OUTPUT,'open-selection-before.png')});
    await select.click();
    const unselect = page.getByRole('button',{name:'Unselect for assistance',exact:true});
    await unselect.waitFor();
    assert(await unselect.isEnabled());
    assert.equal((await page.locator('.ewaf-selection-decision .ewaf-decision-selected').innerText()).trim(), 'Selected for assistance');
    for (const width of [1440,390,320]) {
      await page.setViewportSize({width,height:1000});
      await unselect.scrollIntoViewIfNeeded();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path:path.join(process.env.QA_OUTPUT,`open-selection-${width}.png`)});
    }
    await page.reload();
    await unselect.waitFor();
    assert.deepEqual(errors, []);
    console.log('Open registration selection, CSRF-protected form, selected state, reload and three responsive widths passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
