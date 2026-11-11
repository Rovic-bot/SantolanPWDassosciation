const assert=require('assert/strict'),path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1050},reducedMotion:'reduce'});
  await context.addCookies([{name:process.env.QA_COOKIE_NAME,value:process.env.QA_SESSION,url:process.env.QA_URL}]);
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=500)errors.push(r.url());});
  page.on('dialog',async dialog=>{errors.push('Unexpected dialog');await dialog.dismiss();});
  const url=process.env.QA_URL+process.env.QA_APPLICATION;
  assert.equal((await page.goto(url+'#eligibility',{waitUntil:'networkidle'})).status(),200);
  const status=key=>page.locator(`[data-check="${key}"] .quiet-badge`);
  const clickRow=async(key,target)=>{
   const link=page.locator(`[data-check="${key}"]`);
   await link.focus();await page.keyboard.press('Enter');
   assert.equal(new URL(page.url()).pathname,process.env.QA_APPLICATION);
   assert.equal(new URL(page.url()).hash,'#'+target);
   assert.ok(await page.locator('#'+target).evaluate(node=>node.contains(document.activeElement)));
   assert.ok(await page.locator('#'+target).evaluate(node=>node.classList.contains('review-highlight')));
   if(target!=='documents')assert.ok(await page.locator('#'+target).evaluate(node=>node.open));
  };
  for(const [key,target] of [['membership','membership-review'],['photo','photo-review'],['disability','disability-review'],['documents','documents'],['qualification','program-fit-review']])await clickRow(key,target);
  assert.equal(await page.locator('#program-requirements').evaluate(node=>node.open),true);
  assert.equal(await page.locator('dialog[open]').count(),0);
  const submit=async(button)=>{
   const invalid=await button.evaluate(button=>[...button.form.elements].filter(input=>input.willValidate && !input.validity.valid).map(input=>({name:input.name,message:input.validationMessage})));
   assert.deepEqual(invalid,[], 'Review form has incomplete controls');
   const [response]=await Promise.all([
    page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname===process.env.QA_APPLICATION),
    button.click()
   ]);
   assert.ok([200,302].includes(response.status()));
   await page.waitForFunction(()=>!document.querySelector('form[data-saving]'));
   await page.waitForLoadState('networkidle');
  };
  await clickRow('photo','photo-review');
  assert.equal(await status('photo').innerText(),'Needs review');
  await page.locator('#photo_reason').fill('Fictional authorized review of identity and submitted photograph.');
  await page.locator('#photo_confirm').check();
  await submit(page.getByRole('button',{name:'Verify Identity',exact:true}));
  await page.waitForFunction(()=>document.querySelector('[data-check="photo"] .quiet-badge').textContent==='Verified');
  // Mark Eligible still fails while the program-fit evidence is stale.
  await page.locator('#eligibility_notes').fill('Fictional attempt before program fit is complete.');
  await submit(page.getByRole('button',{name:'Mark Eligible',exact:true}));
  await page.getByText('Verify the current program qualification and functional need below before marking this application Eligible.',{exact:true}).waitFor();
  assert.equal(await status('qualification').innerText(),'Needs review');
  await clickRow('documents','documents');
  for(const input of await page.locator('#program-requirements input[type=radio][value=pass]').all())await input.check();
  await page.locator('#eligibility_notes').fill('Fictional officer checked the complete required submissions.');
  await submit(page.getByRole('button',{name:'Save requirement review',exact:true}));
  await page.waitForFunction(()=>document.querySelector('[data-check="documents"] .quiet-badge').textContent==='Verified');
  await clickRow('qualification','program-fit-review');
  await page.locator('input[name="qualification-value"]').first().check();
  for(const fieldset of await page.locator('#program-fit-review fieldset').all()) {
   const radio=fieldset.locator('input[name^="qualification-outcome_"]');
   if(await radio.count())await radio.first().check();
  }
  await page.locator('input[name="qualification-evidence"][value="'+process.env.QA_PR_EVIDENCE+'"]').check();
  await page.locator('[name="qualification-reason"]').fill('Fictional officer verified each required finding against the cited current evidence.');
  await page.locator('[name="qualification-confirmed"]').check();
  await submit(page.getByRole('button',{name:'Save program fit review',exact:true}));
  await page.waitForFunction(()=>document.querySelector('[data-check="qualification"] .quiet-badge').textContent==='Verified');
  await page.locator('#eligibility_notes').fill('Fictional complete evidence and program qualification reviewed.');
  await submit(page.getByRole('button',{name:'Mark Eligible',exact:true}));
  await page.waitForFunction(()=>document.querySelector('#eligibility [role=status]').textContent==='Eligible');
  await page.locator('#eligibility').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(process.env.QA_OUTPUT,'eligibility-checklist.png')});
  // Preview authorization and current applicant scope remain unchanged.
  const preview=await page.getByRole('link',{name:'Preview',exact:true}).first().getAttribute('href');
  const file=await context.request.get(process.env.QA_URL+preview);
  assert.equal(file.status(),200);assert.ok(file.headers()['cache-control'].includes('no-store'));
  const anonymous=await browser.newContext();
  assert.ok([302,403].includes((await anonymous.request.get(process.env.QA_URL+preview,{maxRedirects:0})).status()));
  await anonymous.close();
  for(const width of [320,390,768,1024,1440]) {
   await page.setViewportSize({width,height:1050});
   for(const [key,target] of [['membership','membership-review'],['photo','photo-review'],['disability','disability-review'],['documents','documents'],['qualification','program-fit-review']]) {
    await clickRow(key,target);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${key} at ${width}`);
   }
   assert.equal(await page.locator('.review-links').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length),width<=700?1:2);
   if(width===390){await page.locator('#eligibility').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.QA_OUTPUT,'eligibility-checklist-mobile.png')});}
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: five same-page checklist targets, keyboard focus and expansion, identity/requirements/program-fit/eligibility saves, unresolved evidence blocked, protected previews, 25 responsive section checks, zero browser errors.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
