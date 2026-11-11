const path=require('path'),fs=require('fs'),assert=require('assert/strict');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||runtime);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const output=path.join(__dirname,'../.local/qa-phase2-results-regression');fs.mkdirSync(output,{recursive:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:650}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const go=async route=>{const r=await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'});assert.equal(r.status(),200,route);};
  const submit=async label=>{await page.getByRole('button',{name:label,exact:true}).click();await page.waitForLoadState('networkidle');};
  const layout=async name=>{
   for(const width of [320,390,768,1024,1440]){
    await page.setViewportSize({width,height:850});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${name} overflow ${width}`);
   }
   await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});
  };
  await go('/accounts/login/');await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);
  await submit('Sign in');await page.waitForURL('**/dashboard/');
  const nav=page.locator('#admin-nav');
  assert.equal(await nav.locator('[data-module-label]').filter({hasText:/^Members$/}).count(),1);
  assert.equal(await nav.getByRole('link',{name:'Member Directory',exact:true}).count(),1);
  assert.equal(await nav.getByRole('link',{name:'Onsite member registration',exact:true}).count(),0);
  assert.equal(await nav.getByRole('link',{name:'Applications',exact:true}).count(),0);
  await nav.getByRole('link',{name:'Member Directory',exact:true}).click();await page.waitForLoadState('networkidle');
  await page.getByRole('navigation',{name:'Member management'}).getByRole('link',{name:'Onsite registration',exact:true}).click();await page.waitForLoadState('networkidle');
  await page.getByRole('heading',{name:'Encode an onsite applicant.'}).waitFor();await layout('onsite-members');
  await page.getByRole('navigation',{name:'Member management'}).getByRole('link',{name:'Membership reviews',exact:true}).click();await page.waitForLoadState('networkidle');
  await page.getByRole('heading',{name:'Membership applications',exact:true}).waitFor();
  await page.setViewportSize({width:1440,height:600});
  const navClick=async name=>{
   const link=nav.getByRole('link',{name,exact:true});await link.scrollIntoViewIfNeeded();
   const before=await nav.evaluate(el=>el.scrollTop);assert.ok(before>0,`${name}: menu must be scrolled`);
   await link.click();await page.waitForLoadState('networkidle');
   const after=await nav.evaluate(el=>el.scrollTop);assert.ok(Math.abs(after-before)<3,`${name}: ${before} -> ${after}`);
  };
  await navClick('Sign-in activity');
  await navClick('Administration changes');
  await navClick('Content Management');
  await page.screenshot({path:path.join(output,'sidebar-preserved.png'),fullPage:true});
  // Mobile reopening restores its own independent menu offset.
  await page.setViewportSize({width:390,height:650});await page.getByRole('button',{name:/Workspace menu/}).click();
  await page.waitForTimeout(400);
  const mobileLink=nav.getByRole('link',{name:'Sign-in activity',exact:true});await mobileLink.scrollIntoViewIfNeeded();
  const mobileBefore=await nav.evaluate(el=>el.scrollTop);assert.ok(mobileBefore>0);
  await mobileLink.click();await page.waitForLoadState('networkidle');
  await page.getByRole('button',{name:/Workspace menu/}).click();await page.waitForTimeout(400);
  assert.ok(Math.abs(await nav.evaluate(el=>el.scrollTop)-mobileBefore)<3,'mobile menu position');
  await page.setViewportSize({width:1440,height:850});
  await go('/announcements/manage/results/'+process.env.QA_PROGRAM+'/');
  await page.locator('#id_reason').fill('Synthetic reviewed final results and privacy review.');await page.locator('#id_confirm').check();
  await submit('Prepare result draft');await page.waitForURL(/\/announcements\/manage\/[0-9a-f-]+\/$/);
  await page.getByRole('heading',{name:'Content preview'}).waitFor();
  const preview=await page.locator('main').innerText();assert.match(preview,/J\*\*\* D\*\*\* C\*\*\*/);assert.ok(!preview.includes(process.env.QA_REFERENCE));
  await layout('result-preview');
  await page.locator('#id_action').selectOption('published');await page.locator('#id_confirm').check();await submit('Apply publication change');
  const publicPath=await page.getByRole('link',{name:/View public announcement/}).getAttribute('href');
  const publicPage=await browser.newPage({viewport:{width:390,height:850}});
  assert.equal((await publicPage.goto(process.env.QA_URL+publicPath)).status(),200);
  const resultText=await publicPage.locator('main').innerText();assert.match(resultText,/J\*\*\* D\*\*\* C\*\*\*/);
  for(const privateValue of [process.env.QA_REFERENCE,'Juan Dela Cruz','BROWSER-ANNOUNCEMENT'])assert.ok(!resultText.includes(privateValue));
  await publicPage.screenshot({path:path.join(output,'public-results-mobile.png'),fullPage:true});
  const resultPath=await publicPage.getByRole('link',{name:'View official result in Results',exact:true}).getAttribute('href');
  assert.match(resultPath,/^\/results\/[0-9a-f-]+\/$/);
  assert.equal((await publicPage.goto(process.env.QA_URL+resultPath)).status(),200);
  const dedicatedText=await publicPage.locator('main').innerText();
  assert.match(dedicatedText,/J\*\*\* D\*\*\* C\*\*\*/);
  for(const privateValue of [process.env.QA_REFERENCE,'Juan Dela Cruz','BROWSER-ANNOUNCEMENT'])assert.ok(!dedicatedText.includes(privateValue));
  assert.equal(await publicPage.locator('#public-nav [aria-current="page"]').innerText(),'Results');
  await publicPage.locator('main .table-responsive').focus();
  assert.equal(await publicPage.locator('main .table-responsive').evaluate(el=>el===document.activeElement),true);
  await publicPage.locator('.display-trigger').click();await publicPage.locator('#display-size').selectOption('largest');
  await publicPage.locator('[data-preference="contrast"]').check();await publicPage.locator('.display-close').click();
  assert.equal(await publicPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Results enlarged text');
  await publicPage.screenshot({path:path.join(output,'dedicated-results-mobile-largest.png'),fullPage:true});
  await publicPage.goto(process.env.QA_URL+'/results/');
  assert.equal(await publicPage.locator(`main a[href="${resultPath}"]`).count(),2);
  assert.equal(await publicPage.locator('#public-nav [aria-current="page"]').innerText(),'Results');
  await publicPage.screenshot({path:path.join(output,'results-list-mobile-largest.png'),fullPage:true});
  await publicPage.close();
  await go(publicPath);await layout('public-results');
  await go(resultPath);await layout('dedicated-results');
  await go('/results/');await layout('results-list');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'passed',desktopAndMobileSidebar:true,unifiedMembers:true,authorizedMaskedResults:true,dedicatedResults:true,resultNoticeLink:true,resultTableKeyboard:true,resultsLargestTextAndContrast:true,widths:[320,390,768,1024,1440],javascriptErrors:0}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
