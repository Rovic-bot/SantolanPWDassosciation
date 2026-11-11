const path=require('path'),fs=require('fs'),assert=require('assert/strict');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||runtime);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const output=path.join(__dirname,'../.local/qa-revised70');fs.mkdirSync(output,{recursive:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const go=async route=>{const r=await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'});assert.equal(r.status(),200,route);};
  const submit=async name=>{await page.getByRole('button',{name,exact:true}).click();await page.waitForLoadState('networkidle');};
  const layout=async name=>{
   for(const width of [320,390,768,1024,1440]){
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${name} overflow at ${width}`);
   }
   await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});
  };
  if(process.argv[2]==='public'){
   for(const route of ['/','/about/','/membership/register/','/contact/','/information/privacy/','/information/accessibility/','/information/ewaf/','/information/faq/','/information/applications/','/announcements/','/events/']){
    await go(route);await layout('public-'+(route.replaceAll('/','-')||'home'));
   }
   await go('/membership/register/');assert.match(await page.locator('main').innerText(),/IN PERSON|in person/);
   assert.equal(await page.locator('main input').count(),0);
   await go('/programs/'+process.env.QA_PROGRAM+'/verify/');
   await page.locator('#id_control_number').fill('BROWSER-REVISED70');await page.locator('#id_full_name').fill('Wrong name');
   await page.locator('#id_birthdate').fill(process.env.QA_BIRTHDATE);await page.locator('#id_contact_number').fill('09170000000');
   await submit('Verify and continue');assert.match(await page.locator('main').innerText(),/Unable to verify membership/);
   await page.locator('#id_full_name').fill('Sample Applicant');await submit('Verify and continue');
   await page.waitForURL('**/apply/');await layout('application');
   const form=page.locator('main form');await form.evaluate(f=>f.requestSubmit());await page.waitForLoadState('networkidle');
   await page.getByRole('alert').first().waitFor();
   await page.locator('#id_calendar_photo').setInputFiles(process.env.QA_PHOTO);
   await form.evaluate(f=>f.requestSubmit());await page.waitForURL('**/submitted/');
   const receipt=await page.locator('main').innerText();assert.match(receipt,/SPWDA-\d{4}-PRG\d{6}-\d{10}/);
   assert.match(receipt,/Results/);assert.doesNotMatch(receipt,/BROWSER-REVISED70|Sample Applicant/);
   assert.match(receipt,/Submission does not guarantee eligibility or selection/);
   assert.match(receipt,/copy command/);
   assert.equal(await page.locator('main a[href="/results/"]').count(),1);
   await layout('receipt');
   await go('/');await page.keyboard.press('Tab');assert.match(await page.locator(':focus').innerText(),/Skip/);
   await page.locator('.display-trigger').click();await page.locator('#display-size').selectOption('largest');
   await page.locator('[data-preference="contrast"]').check();await page.locator('[data-preference="motion"]').check();
   assert.equal(await page.locator('[data-speech-start]').count(),1);
   await page.locator('.display-close').click();await layout('accessible-home');
  }else{
   await go('/accounts/login/');await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);
   await submit('Sign in');await page.waitForURL('**/dashboard/');await layout('dashboard');
   await go('/content/contact/');await page.locator('#id_title').fill('Help Desk information');await page.locator('#id_body').fill('Synthetic approved help instructions.');
   await page.locator('#id_reason').fill('Authorized synthetic CMS publication.');await page.locator('#id_action').selectOption('publish');await submit('Save content action');await layout('content');
   const id=process.env.QA_APPLICATION;
   await go('/programs/photos/');await page.locator('main').getByText(process.env.QA_REFERENCE,{exact:false}).first().waitFor();await layout('photo-queue');
   await go('/programs/photos/'+id+'/');await page.locator('#id_outcome').selectOption('NEEDS_RESUBMISSION');await page.locator('#id_category').fill('Photo clarity');
   await page.locator('#id_reason').fill('Synthetic manual request for clearer evidence.');await page.locator('#id_confirm').check();await submit('Record manual photo review');
   await go('/programs/corrections/'+id+'/');await page.locator('#id_calendar_photo').setInputFiles(process.env.QA_PHOTO);await page.locator('#id_reason').fill('Help Desk assisted synthetic replacement.');
   await submit('Save correction and request review');await page.waitForURL('**/programs/photos/'+id+'/');
   await page.locator('#id_outcome').selectOption('VERIFIED');await page.locator('#id_reason').fill('Synthetic photo manually reviewed against the approved instructions.');await page.locator('#id_confirm').check();
   await submit('Record manual photo review');await layout('photo-review');
   await go('/assistance/'+id+'/review/');await page.locator('#id_eligibility').selectOption('eligible');await page.locator('#id_other_requirements').selectOption('pass');await page.locator('#id_notes').fill('Verified all required evidence.');
   await submit('Assess eligibility');
   await go('/assistance/'+id+'/decision/');await page.locator('#id_decision').selectOption('approved');await page.locator('#id_notes').fill('Synthetic official decision using the published non-EWAF method.');await page.locator('#id_confirm').check();
   await submit('Record administrative decision');assert.match(await page.locator('main').innerText(),/Selected/);
   await go('/assistance/'+id+'/release/');await page.locator('#id_benefit').fill('Synthetic received support');await page.locator('#id_released_on').fill(process.env.QA_DATE);await page.locator('#id_notes').fill('Synthetic actual receipt confirmed.');await page.locator('#id_confirm').check();
   await submit('Confirm assistance release');assert.match(await page.locator('main').innerText(),/Completed|received|released/);await layout('assistance-history');
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({phase:process.argv[2],result:'passed',widths:[320,390,768,1024,1440],javascriptErrors:errors.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
