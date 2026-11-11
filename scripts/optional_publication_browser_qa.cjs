const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs'), assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const origin = process.env.QA_URL, output = process.env.QA_OUTPUT;
  const cookie = {name:'sessionid',value:process.env.QA_SESSION,url:origin};
  try {
    const context = await browser.newContext({reducedMotion:'reduce'});
    await context.addCookies([cookie]);
    const page = await context.newPage(), errors = [], checks = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + process.env.QA_BUILDER);
    for (const name of ['description','benefit']) {
      assert.equal(await page.locator(`textarea[name="${name}"]`).inputValue(),'');
      assert.equal(await page.locator(`textarea[name="${name}"]`).getAttribute('required'),null);
    }
    await page.waitForSelector('[data-readiness="details"][data-complete="true"]');
    for (const dark of [false,true]) {
      for (const width of [1440,390]) {
        await page.setViewportSize({width,height:960});
        await page.goto(origin + process.env.QA_PROGRAM);
        await page.evaluate(dark => document.dispatchEvent(new CustomEvent('santolan:setadmintheme',{detail:dark?'dark':'light'})),dark);
        assert.equal(await page.locator('#program-publication-title').innerText(),'Ready for final approval');
        assert.equal(await page.getByText('Complete this field before publishing.',{exact:false}).count(),0);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.locator('.profile-publication').screenshot({path:`${output}/program-${dark?'dark':'light'}-${width}.png`});
        await page.goto(origin + process.env.QA_EVENT);
        assert(await page.getByRole('link',{name:'Unpublish event',exact:true}).isVisible());
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.locator('.profile-publication').screenshot({path:`${output}/event-${dark?'dark':'light'}-${width}.png`});
        checks.push({dark,width,optionalFields:true,unpublish:true,overflow:false});
      }
    }
    await page.goto(origin + process.env.QA_PROGRAM);
    await page.getByRole('button',{name:'Approve and publish',exact:true}).click();
    await page.getByRole('heading',{name:'Program is live',exact:true}).waitFor();
    const noJS = await browser.newContext({javaScriptEnabled:false});
    await noJS.addCookies([cookie]);
    const fallback = await noJS.newPage();
    await fallback.goto(origin + process.env.QA_EVENT + '?action=draft');
    assert(await fallback.locator('#event-status-form').isVisible());
    assert.equal(await fallback.locator('#event-status-form [name=action]').inputValue(),'draft');
    await noJS.close();
    await page.goto(origin + process.env.QA_EVENTS);
    await page.getByRole('link',{name:'Unpublish event: Synthetic withdrawable event',exact:true}).click();
    const form = page.locator('#event-status-form');
    await form.waitFor({state:'visible'});
    assert.equal(await form.locator('[name=action]').inputValue(),'draft');
    await form.getByRole('textbox',{name:/Reason/}).fill('Synthetic browser withdrawal for schedule review.');
    await form.getByLabel('I confirm this event should be unpublished.',{exact:true}).check();
    await page.locator('.profile-publication').screenshot({path:`${output}/unpublish-review-mobile.png`});
    await form.getByRole('button',{name:'Unpublish event',exact:true}).click();
    await page.waitForURL(url => url.pathname === process.env.QA_EVENT && !url.search);
    assert(await page.getByRole('button',{name:'Publish event',exact:true}).isVisible());
    assert.equal((await page.request.get(origin + process.env.QA_POPUP)).status(),404);
    await page.goto(origin + '/events/');
    assert.equal(await page.getByRole('heading',{name:'Synthetic withdrawable event',exact:true}).count(),0);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,publishedWithBlankText:true,auditedUnpublish:true,privateAfterUnpublish:true,noJSReview:true,errors},null,2));
    console.log('Optional publication UI passed: blank text publication, unpublish review, public withdrawal, four themed layouts, no-JavaScript review.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
