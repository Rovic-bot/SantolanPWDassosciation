const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT, errors = [], checks = [];
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
      ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base + process.env.QA_PROGRAM);
    const details = await page.locator('main').innerText();
    for(const label of ['Program overview','Schedule & capacity','Registration period','Program duration','Planned beneficiary slots','Eligibility profile']) assert.ok(details.toLowerCase().includes(label.toLowerCase()));
    for(const label of ['Purpose and intended benefit','How review and selection work','How program applications work','Selection method','Photo instructions','Configured calendar photo','Applicant statement']) assert.equal(details.includes(label),false);
    await screenshot(page,'public-program-details');
    await page.goto(base + process.env.QA_VERIFY);
    assert.equal(await page.locator('[name="birthdate"], [name="contact_number"]').count(),0);
    await page.locator('[name="control_number"]').fill(process.env.QA_BAD_CONTROL);
    await page.locator('[name="full_name"]').fill(process.env.QA_BAD_NAME);
    await page.getByRole('button',{name:'Verify membership and screen requirements'}).click();
    await page.getByRole('heading',{name:'Application cannot proceed'}).waitFor();
    assert.equal(new URL(page.url()).pathname,process.env.QA_VERIFY);
    const staleToken = await page.locator('[name="csrfmiddlewaretoken"]').inputValue();
    const oldCookie = (await context.cookies()).find(cookie=>cookie.name==='synthetic_program_csrf').value;
    await page.locator('[name="control_number"]').fill(process.env.QA_CONTROL);
    await page.locator('[name="full_name"]').fill(process.env.QA_NAME);

    const staff = await context.newPage();
    staff.on('pageerror',error=>errors.push(error.message));
    await staff.goto(base + process.env.QA_LOGIN);
    await staff.locator('[name="username"]').fill(process.env.QA_USERNAME);
    await staff.locator('[name="password"]').fill(process.env.QA_PASSWORD);
    await Promise.all([staff.waitForURL(url=>url.pathname!==process.env.QA_LOGIN),
      staff.getByRole('button',{name:'Sign in',exact:true}).click()]);
    const newCookie = (await context.cookies()).find(cookie=>cookie.name==='synthetic_program_csrf').value;
    assert.notEqual(newCookie,oldCookie,'A real staff login must rotate the CSRF secret');
    const invalid = await context.request.post(base + process.env.QA_VERIFY,{form:{csrfmiddlewaretoken:staleToken,
      control_number:process.env.QA_CONTROL,full_name:process.env.QA_NAME,version:'0'}});
    assert.equal(invalid.status(),403,'A genuinely stale token must remain rejected by Django');
    assert.equal(await page.locator('[name="full_name"]').inputValue(),process.env.QA_NAME);
    await Promise.all([page.waitForURL(base + process.env.QA_APPLY),
      page.getByRole('button',{name:'Verify membership and screen requirements'}).click()]);
    checks.push('Retry after rejected disability screening and real cross-tab login succeeds without reloading or retyping');
    assert.equal(await page.locator('[name="pwd_id_number"], [name="calendar_photo"]').count(),0);
    const applicationPosts = [];
    page.on('request',request=>{
      if(request.method()==='POST' && new URL(request.url()).pathname===process.env.QA_APPLY) applicationPosts.push(request);
    });
    assert.equal(await page.locator('[name="applicant_contact"]').count(),0);
    assert.equal(await page.locator('[name="current_information"]').inputValue(),'unchanged');
    assert.deepEqual(await page.locator('[name="current_information"] option').evaluateAll(
      options=>options.map(option=>option.value)),['unchanged','changed']);
    const applicationText = await page.locator('main').innerText();
    for(const text of ['Screening passed','Complete the application for Admin review.',
      'Has your employment, household monthly income','For help or corrections, contact the',
      'Relevant verified internal documents are reused','Upload the requested documents and answer',
      'PDF, JPG, JPEG, or PNG only; up to','Consider your employment, household monthly income',
      'Submission is for administrator review and does not confirm',process.env.QA_CONTACT]) assert.equal(applicationText.includes(text),false);
    await page.locator('[name="applicant_email"]').fill('application-only@example.invalid');
    await page.locator('[name="current_information"]').selectOption('changed');
    await page.locator('[name="confirm_information"]').check();
    await page.locator(`[name="${process.env.QA_DOCUMENT_FIELD}"]`).setInputFiles(process.env.QA_FILE);
    await page.locator(`[name="${process.env.QA_DOCUMENT_FIELD}"]`).evaluate(input=>{
      window.selectedProgramInput = input;
      window.selectedProgramFile = input.files[0];
    });
    async function assertUploadRetained() {
      assert.equal(new URL(page.url()).pathname,process.env.QA_APPLY);
      assert.ok(await page.evaluate(()=>window.selectedProgramInput.isConnected &&
        window.selectedProgramInput.files[0]===window.selectedProgramFile && window.selectedProgramFile.size>0));
    }
    await page.getByRole('button',{name:'Submit application',exact:true}).click();
    assert.equal(await page.locator(`[name="${process.env.QA_STATEMENT_FIELD}"]`).evaluate(input=>input.validity.valueMissing),true);
    assert.equal(applicationPosts.length,0);
    await assertUploadRetained();
    await page.locator(`[name="${process.env.QA_STATEMENT_FIELD}"]`).fill('Synthetic program application statement.');
    const invalidSubmission = page.waitForResponse(response=>new URL(response.url()).pathname===process.env.QA_APPLY && response.status()===422);
    await page.getByRole('button',{name:'Submit application',exact:true}).click();
    await invalidSubmission;
    await page.locator('[data-application-errors]:visible').waitFor();
    assert.match(await page.locator('[data-application-errors]').innerText(),/Describe the change/);
    await assertUploadRetained();
    await screenshot(page,'application-validation');
    await page.locator('[name="current_information"]').selectOption('unchanged');
    await page.route(base + process.env.QA_APPLY, route=>route.abort(), {times:1});
    await page.getByRole('button',{name:'Submit application',exact:true}).click();
    await page.getByText('The submission could not be confirmed.',{exact:false}).waitFor();
    await assertUploadRetained();
    checks.push('Same selected File and input survive missing required answer, server-only validation, and failed connection');
    await screenshot(page,'application-form');
    await page.getByRole('button',{name:'Submit application',exact:true}).click();
    await page.locator('[data-program-receipt-dialog] #program-receipt-reference').waitFor();
    assert.equal(new URL(page.url()).pathname,process.env.QA_APPLY);
    const reference = await page.locator('#program-receipt-reference').innerText();
    const anonymous = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    const tracking = await anonymous.newPage();
    tracking.on('pageerror',error=>errors.push(error.message));
    await tracking.goto(base + process.env.QA_TRACK);
    assert.deepEqual(await tracking.locator('form input:not([type=hidden])').evaluateAll(inputs=>inputs.map(input=>input.name)),['reference']);
    await tracking.locator('[name=reference]').fill(reference);
    await tracking.getByRole('button',{name:'View application status'}).click();
    await tracking.getByRole('heading',{name:'Application progress',exact:true}).waitFor();
    const progressText = await tracking.locator('main').innerText();
    assert.match(progressText,/Under review/);
    for(const value of [process.env.QA_NAME,process.env.QA_CONTROL,'application-only@example.invalid',process.env.QA_CONTACT]) {
      assert.equal(progressText.includes(value),false);
    }
    await screenshot(tracking,'reference-only-tracking');
    await anonymous.close();
    checks.push('Anonymous reference-only lookup shows limited application progress without member details or documents');

    await staff.goto(base + process.env.QA_APPS);
    const link = staff.locator('a[href*="/applications/"]').filter({hasText:/View|Review/i}).first();
    await link.click();
    await staff.getByRole('heading',{name:'Application review',exact:true}).waitFor();
    const reviewText = await staff.locator('main').innerText();
    assert.match(reviewText,/application-only@example.invalid/);
    assert.match(reviewText,/Synthetic program application statement/);
    assert.match(reviewText,/Configured calendar photo/);
    for(const text of ['Recorded guardian','Recorded spouse','0001-0002','Household and assistance','Member documents on file']) {
      assert.equal(reviewText.includes(text),false,`${text} leaked into program application review`);
    }
    await screenshot(staff,'application-review');
    await staff.getByRole('button',{name:'Eligible',exact:true}).click();
    await staff.waitForFunction(()=>document.querySelector('.member-title')?.textContent.includes('Eligible'));
    checks.push('Configured evidence is reviewed in system without a duplicate PWD ID or universal photo gate');
    await staff.getByRole('link',{name:'Member record',exact:true}).click();
    await staff.locator('#member-record-registration').waitFor();
    assert.equal(await staff.getByRole('link',{name:'Original membership application',exact:false}).count(),0);
    const original = await staff.locator('#member-record-registration').textContent();
    for(const text of ['Recorded guardian','Recorded spouse','0001-0002','0003-0004','01610']) assert.ok(original.includes(text));
    await screenshot(staff,'member-registration');
    checks.push('Member Directory displays complete original registration; program review excludes it');
    await staff.goto(base + process.env.QA_RANKING);
    const inputs = staff.locator('#readiness');
    await inputs.waitFor();
    for(const label of ['From member registration','Household monthly income','4Ps member','Employment status',
      'Household members','Scoring configuration pending']) assert.ok((await inputs.innerText()).includes(label));
    assert.equal((await inputs.innerText()).includes('Complete the input review'),false);
    assert.equal(await inputs.getByRole('link',{name:'Review ranking inputs',exact:true}).count(),0);
    await staff.getByRole('link',{name:'Review scoring configuration',exact:true}).waitFor();
    await inputs.getByRole('link',{name:'Member record',exact:true}).waitFor();
    for(const theme of ['dark','light']) {
      if(await staff.locator('html').getAttribute('data-dashboard-theme')!==theme) await staff.locator('[data-dashboard-theme-toggle]').click();
      await screenshot(staff,`ranking-registration-${theme}`);
    }
    checks.push('Ranking automatically shows private registration inputs and actionable configuration links without claiming acceptance');
    for(const [name,route] of [['announcements',process.env.QA_ANNOUNCEMENTS],['notices',process.env.QA_NOTICES]]) {
      await staff.goto(base + route);
      const create = staff.getByRole('link',{name:'Create announcement',exact:true});
      await create.waitFor();
      assert.equal(await create.innerText(),'');
      for(const theme of ['light','dark']) {
        if(await staff.locator('html').getAttribute('data-dashboard-theme')!==theme) await staff.locator('[data-dashboard-theme-toggle]').click();
        for(const width of [1440,390]) {
          await staff.setViewportSize({width,height:1000});
          const plusBox=await create.boundingBox(), filterBox=await staff.locator('.announcement-filter-tools form').boundingBox();
          assert.ok(plusBox.x >= filterBox.x + filterBox.width - 1,'Create icon must be to the right of the filters');
          assert.ok(plusBox.width>=44 && plusBox.height>=44,'Accessible touch target');
        }
        await screenshot(staff,`${name}-plus-${theme}`);
      }
      await create.focus();
      await staff.keyboard.press('Enter');
      await staff.waitForURL(base + process.env.QA_CREATE_ANNOUNCEMENT);
      await staff.getByRole('heading',{name:'Create announcement',exact:true}).waitFor();
    }
    checks.push('Announcement plus button stays beside filters, works with keyboard, and fits desktop/mobile in both themes');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({checks,consoleErrors:errors},null,2));
    console.log(JSON.stringify({checks,output}));
    async function screenshot(target,name) {
      for(const width of [1440,390]) {
        await target.setViewportSize({width,height:1000});
        await target.evaluate(()=>document.fonts.ready);
        assert.ok(await target.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${name}/${width} overflow`);
        await target.screenshot({path:path.join(output,`${name}-${width}.png`),fullPage:true});
      }
      await target.setViewportSize({width:1440,height:1000});
    }
  } catch (error) {
    for (const context of browser.contexts()) for (const page of context.pages()) {
      console.error('Failure page:', new URL(page.url()).pathname, (await page.locator('main').innerText().catch(()=>'' )).slice(0,1800));
    }
    throw error;
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
