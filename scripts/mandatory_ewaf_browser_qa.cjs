const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs'), assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const origin = process.env.QA_URL, output = process.env.QA_OUTPUT;
  let page;
  try {
    const context = await browser.newContext({reducedMotion:'reduce'});
    await context.addCookies([{name:'sessionid',value:process.env.QA_SESSION,url:origin}]);
    page = await context.newPage();
    const errors = [], checks = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const dark of [false,true]) {
      for (const width of [1440,390]) {
        await page.setViewportSize({width,height:960});
        await page.goto(origin + process.env.QA_CREATE);
        await page.evaluate(dark => document.dispatchEvent(new CustomEvent('santolan:setadmintheme',{detail:dark?'dark':'light'})),dark);
        assert.equal(await page.locator('[name=ewaf_applicable]').count(),0);
        assert.doesNotMatch(await page.locator('[data-program-builder]').innerText(),/Unlimited|whether this program uses EWAF/);
        const slots = page.locator('[name=slots]');
        assert(await slots.isEnabled());
        assert.equal(await slots.getAttribute('required'),'');
        await page.locator('[name=name]').fill('Synthetic required EWAF setup');
        await page.locator('[name=assistance_type]').selectOption('Food & Nutrition');
        await page.locator('[data-save-draft]').click();
        const summary = page.locator('[data-validation-summary]');
        assert.match(await summary.innerText(),/Beneficiary slots/);
        assert.match(await summary.innerText(),/Select at least one disability type/);
        await slots.fill('0');
        assert.equal(await slots.evaluate(input=>input.checkValidity()),false);
        await slots.fill('4');
        assert.equal(await page.locator('[data-preview-capacity]').innerText(),'4 places');
        await page.locator('[data-select-all-disabilities]').click();
        assert.equal(await page.locator('[name=eligible_disability_types]:checked').count(),10);
        assert.match(await page.locator('[data-readiness=eligibility]').innerText(),/10 selected/);
        await page.locator('[name=eligible_disability_types]').first().uncheck();
        assert.equal(await page.locator('[name=eligible_disability_types]:checked').count(),9);
        await page.locator('[data-select-all-disabilities]').click();
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        await page.locator('#setup-capacity').screenshot({path:`${output}/capacity-${dark?'dark':'light'}-${width}.png`});
        await page.locator('#setup-eligibility').screenshot({path:`${output}/eligibility-${dark?'dark':'light'}-${width}.png`});
        checks.push({dark,width,requiredSlots:true,requiredTypes:true,selectAll:10,noToggle:true,overflow:false});
      }
    }
    await page.locator('[data-save-draft]').click();
    await page.waitForFunction(()=>document.querySelector('[data-program-builder]')?.dataset.saved==='true');
    await page.reload();
    assert.equal(await page.locator('[name=slots]').inputValue(),'4');
    assert.equal(await page.locator('[name=eligible_disability_types]:checked').count(),10);
    assert.equal(await page.locator('[name=ewaf_applicable]').count(),0);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,savedRequiredEWAFDraft:true,errors},null,2));
    console.log('Mandatory EWAF browser passed: four themed viewport checks, required capacity and eligibility, Select all, and persisted draft.');
  } catch(error) {
    if(page&&!page.isClosed()) await page.screenshot({path:`${output}/failure.png`,fullPage:true});
    throw error;
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
