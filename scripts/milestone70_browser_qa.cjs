const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url());});
  const output=path.join(__dirname,'../.local/qa-milestone70');fs.mkdirSync(output,{recursive:true});
  const base='/assistance/'+process.env.QA_APPLICATION+'/',program='/programs/manage/'+process.env.QA_PROGRAM_ID+'/applications/'+process.env.QA_APPLICATION+'/';
  const go=async route=>assert.equal((await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200,route);
  const submit=async title=>{await page.getByRole('button',{name:title,exact:true}).click();await page.waitForLoadState('networkidle');};
  const noOverflow=async()=>{
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)){
    await page.screenshot({path:path.join(output,'overflow.png'),fullPage:true});
    console.error(await page.evaluate(()=>[...document.querySelectorAll('main *')].filter(e=>{const r=e.getBoundingClientRect();return r.right>innerWidth+1||r.left < -1;}).slice(0,15).map(e=>({tag:e.tagName,classes:e.className,text:e.textContent.trim().slice(0,80),width:e.getBoundingClientRect().width}))));
    assert.fail('Overflow: '+page.url()+' at '+page.viewportSize().width);
   }
  };
  await go('/accounts/login/');await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);await submit('Sign in');await page.waitForURL('**/dashboard/');
  await page.getByRole('link',{name:'Review eligibility and assistance',exact:true}).click();await page.getByRole('link',{name:/Open review for/}).click();
  await page.getByRole('link',{name:'View submitted requirements and documents'}).click();
  const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:/Supporting proof.*download/}).click();assert.equal(await (await downloadPromise).failure(),null);
  await page.getByRole('link',{name:'Eligibility and assistance review',exact:true}).click();await page.waitForURL('**'+base);
  const assess=async()=>{
   await go(base+'review/');await page.locator('#id_eligibility').selectOption('eligible');await page.locator('#id_other_requirements').selectOption('pass');await page.locator('#id_notes').fill('Verified the original proof and all program requirements.');
   await page.locator('#id_check_'+process.env.QA_REQUIREMENT_ID).selectOption('pass');await submit('Assess eligibility');await page.waitForURL('**'+base);
  };
  await go(base+'review/');await page.locator('#id_eligibility').selectOption('eligible');await page.locator('#id_other_requirements').selectOption('review');await page.locator('#id_notes').fill('Incomplete review.');await submit('Assess eligibility');await page.getByText('Eligible requires active membership',{exact:false}).waitFor();
  await assess();
  const approve=async()=>{await go(base+'decision/');await page.locator('#id_decision').selectOption('approved');await page.locator('#id_notes').fill('Human administrator approves the assistance.');await page.locator('#id_confirm').check();await submit('Record administrative decision');await page.waitForURL('**'+base);};
  await approve();
  const routes=['/assistance/',base,base+'review/',base+'decision/',base+'release/','/assistance/statuses/','/assistance/statuses/eligible/','/members/'+process.env.QA_MEMBER_ID+'/'];
  let checks=0;
  for(const width of [320,390,768,1024,1440])for(const route of routes){
   await page.setViewportSize({width,height:900});await go(route);await noOverflow();checks++;
   const problems=await page.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return {duplicate:ids.filter((id,i)=>ids.indexOf(id)!==i),unlabelled:[...document.querySelectorAll('input:not([type=hidden]),textarea,select')].filter(e=>!e.labels.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).map(e=>e.id)};});
   assert.deepEqual(problems,{duplicate:[],unlabelled:[]});
   if([320,1440].includes(width)&&[base,base+'review/',base+'release/'].includes(route))await page.screenshot({path:path.join(output,(route===base?'review':route.endsWith('release/')?'release-form':'checklist')+'-'+width+'.png'),fullPage:true});
  }
  for(const route of routes){await page.setViewportSize({width:320,height:900});await go(route);await page.locator('.display-trigger').click();await page.locator('#display-size').selectOption('largest');await page.locator('.display-close').click();await noOverflow();}
  await page.screenshot({path:path.join(output,'member-largest-320.png'),fullPage:true});
  await page.locator('.display-trigger').click();await page.locator('#display-size').selectOption('default');await page.locator('.display-close').click();
  await page.setViewportSize({width:1440,height:1000});
  await go('/assistance/statuses/eligible/');await page.locator('#id_label').fill('Requirements met');await page.locator('#id_notes').fill('Use association wording.');await submit('Save eligibility label');await page.waitForURL('**/assistance/statuses/');
  await go(base);assert.equal(await page.locator('.quiet-badge').filter({hasText:'Eligible'}).count(),1);
  const release=async()=>{
   await go(base+'release/');await page.locator('#id_assistance_type').fill('Delivered support');await page.locator('#id_benefit').fill('Private synthetic assistance benefit');await page.locator('#id_amount').fill('500');await page.locator('#id_reference').fill('RECEIPT-QA-70');
   const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Manila',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());await page.locator('#id_released_on').fill(today);
   await page.locator('#id_notes').fill('Confirmed actual delivery to the member.');await page.locator('#id_confirm').check();
   await page.locator('#id_confirm').focus();await page.keyboard.press('Tab');
   assert.equal(await page.getByRole('button',{name:'Confirm assistance release'}).evaluate(e=>document.activeElement===e),true);
   assert.equal(await page.getByRole('button',{name:'Confirm assistance release'}).evaluate(e=>getComputedStyle(e).outlineWidth),'3px');
   await submit('Confirm assistance release');await page.waitForURL('**'+base);
  };
  await release();await page.getByText('Successful releases across this member’s programs: 1',{exact:false}).waitFor();
  await page.screenshot({path:path.join(output,'released-desktop.png'),fullPage:true});
  await page.getByRole('link',{name:'Void incorrect release'}).click();const voidRoute=new URL(page.url()).pathname;
  for(const width of [320,390,768,1024,1440]){await page.setViewportSize({width,height:900});await noOverflow();checks++;}
  await page.locator('#id_notes').fill('Incorrect recorded amount; void and retain before correction.');await page.locator('#id_confirm').check();await submit('Void incorrect release');await page.waitForURL('**'+base);
  await page.getByText('Successful releases across this member’s programs: 0',{exact:false}).waitFor();
  await assess();await approve();await release();
  await go('/members/'+process.env.QA_MEMBER_ID+'/');await page.getByText('Successfully received assistance: 1',{exact:false}).waitFor();
  await page.setViewportSize({width:320,height:900});await noOverflow();await page.screenshot({path:path.join(output,'member-releases-mobile.png'),fullPage:true});
  await page.emulateMedia({reducedMotion:'reduce'});await go('/');assert.equal(await page.locator('[data-sculpture]').evaluate(e=>getComputedStyle(e).transform),'none');
  assert.deepEqual(errors,[]);
  const report={status:'pass',responsiveChecks:checks,enlargedTextChecks:routes.length,errors,workflows:['private document review','eligibility validation','human approval','label configuration with retained history','confirmed release','void and replacement','successful-only member count','keyboard focus','reduced motion']};
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
