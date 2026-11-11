const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs'), assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const origin = process.env.QA_URL, output = process.env.QA_OUTPUT;
  let page;
  try {
    const context = await browser.newContext({reducedMotion:'reduce'});
    await context.addCookies([{name:'sessionid', value:process.env.QA_SESSION, url:origin}]);
    page = await context.newPage();
    const errors = [], checks = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const dark of [false,true]) {
      for (const width of [1440,390]) {
        await page.setViewportSize({width,height:960});
        await page.goto(origin + process.env.QA_DRAFT);
        await page.evaluate(dark => document.dispatchEvent(new CustomEvent('santolan:setadmintheme',{detail:dark?'dark':'light'})),dark);
        const toggle = page.locator('[name=ewaf_applicable]'), slots = page.locator('[name=slots]');
        const disability = page.locator('[name=eligible_disability_types]').first();
        assert.equal(await page.locator('[name=eligible_disability_types]:checked').count(),0);
        assert.match(await page.locator('[data-readiness=eligibility]').innerText(), /All disability types included/);
        await disability.check();
        assert.match(await page.locator('[data-readiness=eligibility]').innerText(), /1 selected/);
        await disability.uncheck();
        assert.match(await page.locator('[data-readiness=eligibility]').innerText(), /All disability types included/);
        assert(await toggle.isChecked());
        assert(await slots.isEnabled());
        assert.equal(await page.locator('[data-preview-capacity]').innerText(), 'Not set');
        assert.match(await page.locator('[data-readiness=capacity]').innerText(), /Beneficiary slots required for EWAF/);
        await toggle.uncheck();
        assert(await slots.isDisabled());
        assert.equal(await page.locator('[data-preview-capacity]').innerText(), 'Unlimited');
        assert.match(await page.locator('[data-preview-selection]').innerText(), /automatically selected/);
        await toggle.check();
        await slots.fill('3');
        assert.equal(await page.locator('[data-preview-capacity]').innerText(), '3 places');
        await toggle.uncheck();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.locator('#setup-capacity').screenshot({path:`${output}/capacity-${dark?'dark':'light'}-${width}.png`});
        checks.push({dark,width,toggle:true,unlimited:true,overflow:false});
      }
    }
    await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes(process.env.QA_DRAFT)),
      page.getByRole('button',{name:'Update program',exact:true}).click()
    ]);
    await page.waitForFunction(() => /updated|saved/i.test(document.querySelector('[data-save-feedback]')?.textContent || ''));
    await page.goto(origin + process.env.QA_DRAFT);
    assert.equal(await page.locator('[name=ewaf_applicable]').isChecked(),false);
    assert.equal(await page.locator('[name=slots]').inputValue(),'');
    for (const dark of [false,true]) {
      for (const width of [1440,390]) {
        await page.setViewportSize({width,height:960});
        await page.goto(origin + process.env.QA_PROFILE);
        await page.evaluate(dark => document.dispatchEvent(new CustomEvent('santolan:setadmintheme',{detail:dark?'dark':'light'})),dark);
        const profile = page.locator('.profile-eligibility-section');
        assert.match(await profile.innerText(), /All disability types are automatically included/);
        assert.equal(await profile.locator('li[data-active=true]').count(),10);
        assert.equal(await profile.getByText('Included',{exact:true}).count(),10);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await profile.screenshot({path:`${output}/eligibility-${dark?'dark':'light'}-${width}.png`});
      }
    }
    await page.goto(origin + process.env.QA_APPLICATION);
    assert.match(await page.locator('#eligibility-decision-form').innerText(), /automatically selects this applicant/);
    await page.getByRole('button',{name:'Eligible',exact:true}).click();
    await page.waitForFunction(() => !document.querySelector('#eligibility-decision-form'));
    assert.match(await page.locator('body').innerText(), /automatically selected/);
    await page.goto(origin + process.env.QA_RESULTS);
    assert.match(await page.locator('.results-capacity-chip').first().innerText(), /Unlimited/);
    assert.match(await page.locator('.results-publication-note').innerText(), /No certificate emails/);
    await page.getByRole('button',{name:'Publish results',exact:true}).click();
    await page.waitForFunction(() => /Program results published|Results published/.test(document.body.innerText));
    await page.goto(origin + process.env.QA_RESULTS);
    assert.match(await page.locator('.results-selected-chip').innerText(), /1/);
    assert.equal(await page.getByRole('button',{name:/Retry.*email/}).count(),0);
    await page.screenshot({path:`${output}/published-results.png`,fullPage:true});
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,blankDisabilityIncludesAll:true,autoSelected:true,published:true,certificateEmails:false,errors},null,2));
    console.log('Non-EWAF browser passed: four themed viewport checks, saved unlimited draft, automatic Eligible selection, and explicit result publication without certificate emails.');
  } catch(error) {
    if (page && !page.isClosed()) await page.screenshot({path:`${output}/failure.png`,fullPage:true});
    throw error;
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
