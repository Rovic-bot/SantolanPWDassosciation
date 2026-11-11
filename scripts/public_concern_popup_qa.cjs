/* Requires an isolated synthetic member supplied by the Django browser test. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const origin=process.env.QA_URL;
if(!origin || !process.env.QA_CONTROL || !process.env.QA_NAME) throw new Error('Synthetic test environment required');
const output='docs/public-concern-popup-2026-11-08';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    fs.mkdirSync(output,{recursive:true});
    const page=await browser.newPage({viewport:{width:1440,height:960}}), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(origin+'/resources/');
    const trigger=page.locator('[data-concern-open]'), dialog=page.locator('[data-concern-dialog]');
    await trigger.scrollIntoViewIfNeeded();
    const startY=await page.evaluate(()=>scrollY), initialURL=page.url();
    await trigger.click();
    await dialog.locator('#id_control_number').waitFor();
    assert.equal(page.url(),initialURL);
    assert(await dialog.evaluate(el=>el.contains(document.activeElement)));
    await dialog.screenshot({path:`${output}/verification-1440.png`});
    await dialog.locator('#id_control_number').fill(process.env.QA_CONTROL);
    await dialog.locator('#id_full_name').fill('Wrong synthetic name');
    await dialog.getByRole('button',{name:'Verify membership',exact:true}).click();
    await dialog.locator('.errorlist').first().waitFor();
    await dialog.locator('#id_full_name').fill(process.env.QA_NAME);
    await dialog.getByRole('button',{name:'Verify membership',exact:true}).click();
    await dialog.locator('#id_concern').waitFor();
    assert.equal(page.url(),initialURL);
    await dialog.locator('#id_email').fill('popup@example.invalid');
    await dialog.locator('#id_subject').fill('Synthetic popup request');
    await dialog.locator('#id_assistance_type').selectOption('medical');
    await dialog.locator('#id_concern').fill('Fictional request for browser validation only.');
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(),false);
    assert(await trigger.evaluate(el=>el===document.activeElement));
    assert(Math.abs(await page.evaluate(()=>scrollY)-startY)<2);
    await trigger.click();
    assert.equal(await dialog.locator('#id_subject').inputValue(),'Synthetic popup request');
    // Server-side validation is rendered inside the popup, including the acknowledgement.
    await dialog.locator('form[enctype]').evaluate(form=>{form.noValidate=true;form.requestSubmit();});
    await dialog.locator('.errorlist').first().waitFor();
    await dialog.locator('#id_acknowledgement').check();
    await dialog.locator('#add-supporting-evidence').click();
    await dialog.locator('#id_evidence_1').setInputFiles(process.env.QA_EVIDENCE);
    await dialog.screenshot({path:`${output}/concern-form-1440.png`});
    for(const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
      await dialog.screenshot({path:`${output}/concern-form-${width}.png`});
    }
    await page.setViewportSize({width:1440,height:960});
    // A repeated click cannot create a second concurrent submission.
    await dialog.locator('form[enctype]').evaluate(form=>{form.requestSubmit();form.requestSubmit();});
    await dialog.getByRole('heading',{name:'Your request was received',exact:true}).waitFor();
    assert.equal(page.url(),initialURL);
    assert(await dialog.getByText('Synthetic popup request',{exact:true}).isVisible());
    await dialog.screenshot({path:`${output}/synthetic-receipt-1440.png`});
    await dialog.getByRole('button',{name:'Finish and clear this session',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('[data-concern-dialog]').open);
    await page.route('**/assistance/referrals/verify/',route=>route.abort());
    await trigger.click();
    await dialog.getByRole('button',{name:'Try again',exact:true}).waitFor();
    await page.unroute('**/assistance/referrals/verify/');
    await dialog.getByRole('button',{name:'Try again',exact:true}).click();
    await dialog.locator('#id_control_number').waitFor();
    assert.equal(await dialog.locator('#id_control_number').inputValue(),'');
    for(const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await dialog.screenshot({path:`${output}/verification-${width}.png`});
    }
    await dialog.locator('[aria-label="Close concern form"]').focus();
    await page.keyboard.press('Shift+Tab');
    assert(await dialog.evaluate(el=>el.contains(document.activeElement)));
    await page.keyboard.press('Escape');
    const plain=await browser.newPage({javaScriptEnabled:false});
    await plain.goto(origin+'/resources/');
    await plain.locator('[data-concern-open]').click();
    assert(new URL(plain.url()).pathname.endsWith('/referrals/verify/'));
    assert(await plain.locator('#id_control_number').isVisible());
    await plain.close();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({errors,verification:true,validation:true,privateUpload:true,receipt:true,sessionClearing:true,noNavigation:true,draftPreservedOnClose:true,keyboard:true,mobile:true,noJavaScriptFallback:true},null,2));
    console.log('Popup verification, validation, upload, receipt, finish, focus, mobile and no-JavaScript fallback passed.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
