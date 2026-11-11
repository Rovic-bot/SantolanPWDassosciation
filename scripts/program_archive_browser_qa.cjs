const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs'), assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const origin = process.env.QA_URL, output = process.env.QA_OUTPUT;
  const cookie = {name:'sessionid', value:process.env.QA_SESSION, url:origin};
  let activePage;
  try {
    const context = await browser.newContext({reducedMotion:'reduce'});
    await context.addCookies([cookie]);
    const page = await context.newPage(), errors = [], checks = [];
    activePage = page;
    page.on('pageerror', error => errors.push(error.message));
    for (const dark of [false,true]) {
      for (const width of [1440,390]) {
        await page.setViewportSize({width,height:960});
        await page.goto(origin + process.env.QA_PUBLISHED);
        await page.evaluate(dark => document.dispatchEvent(new CustomEvent('santolan:setadmintheme',{detail:dark?'dark':'light'})),dark);
        assert(await page.locator('.profile-archive-button').isVisible());
        assert.equal(await page.locator('.profile-archive-button').innerText(),'Unpublish and archive');
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.locator('.profile-publication').screenshot({path:`${output}/button-${dark?'dark':'light'}-${width}.png`});
        await page.goto(origin + process.env.QA_DRAFT);
        assert.equal(await page.locator('.profile-archive-button').innerText(),'Archive program');
        await page.goto(origin + process.env.QA_PORTFOLIO);
        await page.getByRole('link',{name:'Unpublish and archive: Synthetic published program',exact:true}).click();
        const dialog = page.locator('#program-details-dialog');
        const form = dialog.locator('[data-program-archive-review]');
        await form.waitFor({state:'visible'});
        assert.equal(await form.locator('[name=action]').inputValue(),'unpublish');
        assert.equal(await form.locator('[name=action]').getAttribute('type'),'hidden');
        await page.waitForFunction(() => document.activeElement?.name === 'notes');
        assert.equal(new URL(page.url()).pathname,process.env.QA_PORTFOLIO);
        assert(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth + 1));
        await dialog.locator('.profile-publication').screenshot({path:`${output}/review-${dark?'dark':'light'}-${width}.png`});
        await form.getByRole('link',{name:'Cancel',exact:true}).click();
        await dialog.locator('.profile-archive-button').waitFor({state:'visible'});
        assert.equal(new URL(page.url()).pathname,process.env.QA_PORTFOLIO);
        await dialog.locator('.profile-archive-button').click();
        await form.waitFor({state:'visible'});
        assert.equal(await form.evaluate(node => node.checkValidity()),false);
        await dialog.getByRole('button',{name:'Close program details',exact:true}).click();
        checks.push({dark,width,buttons:true,popupReview:true,cancel:true,overflow:false});
      }
    }
    await page.goto(origin + process.env.QA_PORTFOLIO);
    await page.getByRole('link',{name:'Unpublish and archive: Synthetic published program',exact:true}).click();
    const dialog = page.locator('#program-details-dialog');
    const form = dialog.locator('[data-program-archive-review]');
    await form.getByRole('textbox',{name:/Reason/}).fill('Synthetic program withdrawal.');
    await form.getByLabel('I confirm this program should be unpublished and archived.',{exact:true}).check();
    await form.getByRole('button',{name:'Unpublish and archive',exact:true}).click();
    await dialog.getByRole('heading',{name:'Program archived',exact:true}).waitFor();
    assert.equal(new URL(page.url()).pathname,process.env.QA_PORTFOLIO);
    assert.equal(await dialog.locator('.profile-archive-button').count(),0);
    assert.equal((await page.request.get(origin + process.env.QA_PUBLIC)).status(),404);
    await dialog.getByRole('button',{name:'Close program details',exact:true}).click();
    const noJS = await browser.newContext({javaScriptEnabled:false,reducedMotion:'reduce',viewport:{width:1440,height:960}});
    await noJS.addCookies([cookie]);
    const fallback = await noJS.newPage();
    activePage = fallback;
    await fallback.bringToFront();
    await fallback.goto(origin + process.env.QA_DRAFT);
    await fallback.getByRole('link',{name:'Archive program',exact:true}).click();
    const archive = fallback.locator('[data-program-archive-review]');
    assert(await archive.isVisible());
    assert.equal(await archive.locator('[name=action]').inputValue(),'archived');
    await archive.getByRole('textbox',{name:/Reason/}).fill('Synthetic unused draft archived.');
    await archive.getByLabel('I confirm this program should be archived.',{exact:true}).check();
    await archive.getByRole('button',{name:'Archive program',exact:true}).click();
    await fallback.getByRole('heading',{name:'Program archived',exact:true}).waitFor();
    await noJS.close();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,popupUnpublish:true,draftArchiveWithoutJS:true,privateAfterUnpublish:true,errors},null,2));
    console.log('Program archive UI passed: four themed layouts, popup review/cancel/submission, private withdrawal, and draft archiving without JavaScript.');
  } catch (error) {
    if (activePage && !activePage.isClosed()) await activePage.screenshot({path:`${output}/failure.png`,fullPage:true});
    throw error;
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
