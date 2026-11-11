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
    const scores = await page.locator('tbody .receipt-score').allTextContents();
    const applicants = JSON.parse(process.env.QA_APPLICANTS);
    assert.equal(await page.locator('.receipt-action-form').count(), 2);
    for (const [index, applicant] of applicants.entries()) {
      const row = page.locator(`#receipt-${applicant}`);
      await row.locator('.receipt-action-form button').click();
      await row.locator('.receipt-action .receipt-recorded').waitFor();
      assert.equal((await row.locator('.receipt-delivery > .receipt-recorded').innerText()).trim(), 'Received');
      assert.doesNotMatch(await page.locator('main').innerText(), /Receipt was not recorded|APPLICATION_NOT_CANDIDATE|APPLICATION_REVIEW_UNRESOLVED/);
      assert.equal(await page.locator('.receipt-action-form').count(), 1 - index);
      if (index === 0) await page.screenshot({path:path.join(process.env.QA_OUTPUT,'first-receipt.png')});
    }
    assert.deepEqual(await page.locator('tbody .receipt-score').allTextContents(), scores);
    await page.reload();
    assert.equal(await page.locator('.receipt-action .receipt-recorded').count(), 2);
    for (const width of [1440,390]) {
      await page.setViewportSize({width,height:1000});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path:path.join(process.env.QA_OUTPUT,`both-receipts-${width}.png`)});
    }
    assert.deepEqual(errors, []);
    console.log('Both same-day receipt buttons succeeded, recorded states survived reload, scores stayed unchanged, and desktop/mobile checks passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
