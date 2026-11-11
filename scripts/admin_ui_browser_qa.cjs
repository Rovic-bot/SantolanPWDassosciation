const path=require('path'),fs=require('fs'),assert=require('assert/strict');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||runtime);
(async()=>{
 const stage=process.env.QA_UI_STAGE||'after';assert.ok(['before','after'].includes(stage));
 const output=path.join(__dirname,'../.local/qa-admin-ui-cleanup',stage);fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto(process.env.QA_URL+'/accounts/login/');
  await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/dashboard/');
  const labels=['Dashboard','Members','Programs & Events','Applications & Verification','EWAF & Selection','Announcements & CMS','Reports & Exports','Administration'];
  const routes=[['dashboard','/dashboard/'],['members','/members/'],['programs','/programs/manage/'],
   ['program-form','/programs/manage/new/'],['events','/events/manage/'],['applications','/workspace/applications/'],
   ['application-list',`/programs/manage/${process.env.QA_PROGRAM}/applications/`],['photo-review','/programs/photos/'],
   ['selection','/assistance/?eligibility=eligible'],['ewaf','/ewaf/configuration/new/'],
   ['announcements','/announcements/manage/'],['cms','/content/'],['administration','/admin/documents/documenttype/'],
   ['administration-form','/admin/documents/documenttype/add/']];
  const metrics=[];
  for(const [name,route] of routes){
   assert.equal((await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200,route);
   assert.deepEqual(await page.locator('#admin-nav [data-module-label]').allTextContents(),labels);
   for(const width of [320,390,768,1024,1440]){
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${name} document overflow ${width}`);
    if(stage==='after'&&await page.locator('.object-tools').count()){
     const heading=await page.locator('main h1').first().boundingBox(),actions=await page.locator('.object-tools').boundingBox();
     assert.ok(actions.y>=heading.y+heading.height,`${name} actions overlap title at ${width}`);
    }
    if(stage==='after'&&width===1440){
     const icons=await page.locator('.workspace-icon').evaluateAll(items=>items.map(el=>({fill:getComputedStyle(el).fill,stroke:getComputedStyle(el).stroke,width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height})));
     for(const icon of icons){assert.equal(icon.fill,'none');assert.notEqual(icon.stroke,'none');assert.equal(icon.width,18);assert.equal(icon.height,18);}
     const summaries=await page.locator('#admin-nav summary').evaluateAll(items=>items.map(el=>({background:getComputedStyle(el).backgroundColor,color:getComputedStyle(el).color,border:getComputedStyle(el).borderTopWidth})));
     for(const summary of summaries){
      assert.ok(summary.background==='rgba(0, 0, 0, 0)'||summary.background.match(/\d+/g).slice(0,3).map(Number).every(channel=>channel>=200),`${name}: native fieldset styling leaked into navigation`);
      assert.notEqual(summary.color,'rgb(255, 255, 255)');assert.equal(summary.border,'0px');
     }
     metrics.push({page:name,icons:icons.length,title:await page.locator('main h1').first().evaluate(el=>getComputedStyle(el).fontSize)});
    }
    if([390,1440].includes(width))await page.screenshot({path:path.join(output,`${name}-${width}.png`),fullPage:name==='dashboard'&&width===1440});
   }
  }
  // Exercise real GET filters and linked records, without mutating business data.
  await page.goto(process.env.QA_URL+'/programs/manage/');await page.locator('#search').fill('Mobility');
  await page.getByRole('button',{name:'Filter programs',exact:true}).click();await page.waitForLoadState('networkidle');
  assert.equal(await page.locator('tbody tr').count(),1);assert.match(await page.locator('tbody').innerText(),/Sample Mobility assistance/);
  await page.locator('tbody a').first().click();await page.waitForLoadState('networkidle');assert.match(await page.locator('h1').innerText(),/Sample Mobility assistance/);
  await page.goto(process.env.QA_URL+'/members/?q=nonexistent-synthetic-record');
  assert.match(await page.locator('main').innerText(),/No members found/);await page.screenshot({path:path.join(output,'empty-state.png')});
  await page.goto(process.env.QA_URL+'/programs/manage/');await page.setViewportSize({width:390,height:850});
  const menu=page.getByRole('button',{name:/Workspace menu/});await menu.click();await page.waitForTimeout(350);
  await page.screenshot({path:path.join(output,'mobile-navigation.png')});
  await page.locator('#admin-nav summary').first().focus();await page.keyboard.press('Escape');await page.waitForTimeout(350);
  assert.equal(await menu.getAttribute('aria-expanded'),'false');assert.equal(await menu.evaluate(el=>el===document.activeElement),true);
  await page.locator('.display-trigger').click();await page.locator('#display-size').selectOption('largest');
  await page.locator('[data-preference="contrast"]').check();await page.locator('.display-close').click();
  await page.setViewportSize({width:320,height:850});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'enlarged-text overflow');
  await page.screenshot({path:path.join(output,'programs-largest-contrast.png')});
  // Reproduce the reported solid shapes by withholding only the Admin CSS.
  const fallback=await browser.newPage({viewport:{width:1440,height:1000}});
  await fallback.context().addCookies(await page.context().cookies());
  await fallback.route('**/static/css/admin*.css*',route=>route.fulfill({status:200,contentType:'text/css',body:''}));
  await fallback.goto(process.env.QA_URL+'/dashboard/',{waitUntil:'networkidle'});
  await fallback.locator('#admin-nav').evaluate(el=>el.style.display='block');
  const fallbackIcons=await fallback.locator('.workspace-icon,.workspace-chevron').evaluateAll(items=>items.map(el=>({fill:getComputedStyle(el).fill,stroke:getComputedStyle(el).stroke,width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height})));
  if(stage==='before')assert.ok(fallbackIcons.some(icon=>icon.fill==='rgb(0, 0, 0)'&&icon.stroke==='none'));
  else for(const icon of fallbackIcons){assert.equal(icon.fill,'none');assert.notEqual(icon.stroke,'none');assert.ok(icon.width<=18&&icon.height<=18);}
  await fallback.screenshot({path:path.join(output,'icons-without-admin-css.png')});await fallback.close();
  assert.deepEqual(errors,[]);
  const result={result:'passed',stage,pages:routes.length,widths:[320,390,768,1024,1440],normalErrors:errors,metrics,fallbackIcons};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify({result:result.result,stage,pages:routes.length,widths:result.widths,iconsWithoutStyles:stage==='after'?'outlined and bounded':'solid black reproduced',javascriptErrors:0}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
