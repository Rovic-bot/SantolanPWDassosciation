const path=require('path'),fs=require('fs'),assert=require('assert/strict');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||runtime);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const visualStage=process.env.QA_VISUAL_STAGE||'after';
 assert.ok(['before','after'].includes(visualStage),'supported screenshot stage');
 const output=path.join(__dirname,'../.local/qa-admin-navigation-ui/'+visualStage);fs.mkdirSync(output,{recursive:true});
 const errors=[],consoleErrors=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:650},reducedMotion:'reduce'});
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error'&&!/status of 403/.test(message.text()))consoleErrors.push(message.text());});
  const go=async(route,status=200)=>assert.equal((await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),status,route);
  const login=async(target,user)=>{
   await target.goto(process.env.QA_URL+'/accounts/login/');await target.locator('#id_username').fill(user);
   await target.locator('#id_password').fill(process.env.QA_PASSWORD);await target.getByRole('button',{name:'Sign in',exact:true}).click();
   await target.waitForURL('**/dashboard/');
  };
  await login(page,process.env.QA_USERNAME);
  const nav=page.locator('#admin-nav'), labels=['Dashboard','Members','Programs & Events','Applications & Verification','EWAF & Selection','Announcements & CMS','Reports & Exports','Administration'];
  const groups=nav.locator('[data-module-label]');
  assert.deepEqual(await groups.allTextContents(),labels);
  const hrefs=await nav.locator('nav a').evaluateAll(links=>links.map(link=>link.getAttribute('href')));
  assert.equal(hrefs.length,new Set(hrefs).size,'unique navigation destinations');
  const current=async(key)=>assert.deepEqual(await nav.locator('[data-current="true"]').evaluateAll(items=>items.map(item=>item.dataset.groupKey)),[key]);
  await current('dashboard');
  const contrastChecks=[];
  const inspectAppearance=async()=>{
   const checks=await nav.evaluate(el=>{
    const luminance=css=>{
     const values=css.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{
      const channel=v/255;return channel<=.04045?channel/12.92:Math.pow((channel+.055)/1.055,2.4);
     });return .2126*values[0]+.7152*values[1]+.0722*values[2];
    };
    return [...el.querySelectorAll('summary,nav a,.workspace-module-notice,.account-label,.workspace-account strong,.workspace-account a,.workspace-account button')].map(item=>{
     const style=getComputedStyle(item);let ancestor=item;
     while(getComputedStyle(ancestor).backgroundColor==='rgba(0, 0, 0, 0)')ancestor=ancestor.parentElement;
     const fg=luminance(style.color),bg=luminance(getComputedStyle(ancestor).backgroundColor);
     return {label:item.textContent.trim(),ratio:(Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05)};
    });
   });
   for(const check of checks)assert.ok(check.ratio>=4.5,`${check.label}: contrast ${check.ratio}`);
   contrastChecks.push(...checks);
   const icons=await nav.locator('summary .workspace-icon').evaluateAll(items=>items.map(item=>({
    width:item.getBoundingClientRect().width,height:item.getBoundingClientRect().height,
    hidden:item.getAttribute('aria-hidden'),focusable:item.getAttribute('focusable'),
   })));
   assert.equal(icons.length,8);
   for(const icon of icons)assert.deepEqual(icon,{width:18,height:18,hidden:'true',focusable:'false'});
   assert.equal(await nav.locator('summary').evaluateAll(items=>items.every(item=>item.getBoundingClientRect().height>=44)),true);
   const brand=await page.locator('.workspace-brand').evaluate(item=>({color:getComputedStyle(item).color,font:getComputedStyle(item).fontFamily}));
   assert.notEqual(brand.color,'rgb(255, 255, 255)');assert.match(brand.font,/Inter|Segoe UI/);
  };
  if(visualStage){
   for(const width of [320,390,768,1024,1440]){
    await page.setViewportSize({width,height:850});
    if(width<1100){await page.getByRole('button',{name:/Workspace menu/}).click();await page.waitForTimeout(350);}
    await nav.evaluate(el=>el.scrollTop=0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`dashboard overflow at ${width}`);
    if(width===1440)assert.equal(await page.locator('.workspace-sidebar').evaluate(el=>el.getBoundingClientRect().width),252);
    if(visualStage==='after')await inspectAppearance();
    await page.screenshot({path:path.join(output,`dashboard-${width}.png`),fullPage:true});
    if(width<1100){await page.keyboard.press('Escape');await page.waitForTimeout(350);}
   }
  }
  const layout=async(name)=>{
   for(const width of [320,390,768,1024,1440]){
    await page.setViewportSize({width,height:850});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${name} overflow at ${width}`);
   }
   await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});
  };
  const routes=[['/members/','members','members'],['/membership/applications/new/','members','onsite'],
   ['/membership/applications/','members','reviews'],['/workspace/applications/','applications','applications'],
   ['/programs/photos/','applications','photos'],['/assistance/?eligibility=eligible','selection','selection'],
   ['/announcements/manage/results/','content','result-preparation'],['/content/','content','cms'],
   ['/admin/documents/documenttype/','administration','native-documents']];
  for(const [route,key,name] of routes){await go(route);await current(key);assert.deepEqual(await groups.allTextContents(),labels);await layout(name);}
  await go('/workspace/applications/');
  if(visualStage==='after'){
   await page.setViewportSize({width:1440,height:850});
   await nav.locator('details').evaluateAll(items=>items.forEach(item=>item.open=false));
   await nav.evaluate(el=>el.scrollTop=0);
   await page.screenshot({path:path.join(output,'eight-module-overview.png')});
   await nav.locator('details').evaluateAll(items=>items.forEach(item=>item.open=true));
   await page.emulateMedia({forcedColors:'active'});
   assert.equal(await page.locator('.workspace-sidebar').evaluate(el=>getComputedStyle(el).forcedColorAdjust),'auto');
   await page.screenshot({path:path.join(output,'forced-colors.png')});
   await page.emulateMedia({forcedColors:'none'});
  }
  const applicationPath='/programs/manage/'+process.env.QA_PROGRAM+'/applications/';
  assert.equal(await page.locator(`main a[href="${applicationPath}"]`).count(),1);
  await page.locator(`main a[href="${applicationPath}"]`).click();await page.waitForLoadState('networkidle');await current('applications');
  await go('/ewaf/configuration/new/');await current('selection');
  assert.match(await page.locator('main').innerText(),/Historical calculations remain read-only/);
  assert.equal(await page.locator('main form').count(),0);
  assert.match(await nav.locator('[data-group-key="reports"]').innerText(),/Reports and exports are not yet available/);
  assert.equal(await nav.locator('[data-group-key="reports"] a').count(),0);
  await layout('ewaf-unavailable');
  // Native details provides keyboard disclosure; saved state precedes scroll restoration.
  await go('/dashboard/');
  const programs=nav.locator('[data-group-key="programs"]');
  await programs.locator('summary').focus();
  assert.ok(parseFloat(await programs.locator('summary').evaluate(el=>getComputedStyle(el).outlineWidth))>=3);
  await page.keyboard.press('Enter');assert.equal(await programs.evaluate(el=>el.open),false);
  await page.keyboard.press('Tab');assert.equal(await nav.locator('[data-group-key="applications"] summary').evaluate(el=>el===document.activeElement),true);
  await nav.getByRole('link',{name:'Content Management',exact:true}).click();await page.waitForLoadState('networkidle');
  assert.equal(await programs.evaluate(el=>el.open),false,'collapsed group survives navigation');
  const navClick=async(name)=>{
   const link=nav.getByRole('link',{name,exact:true});await link.scrollIntoViewIfNeeded();
   const before=await nav.evaluate(el=>el.scrollTop);assert.ok(before>0);
   await link.click();await page.waitForLoadState('networkidle');
   assert.ok(Math.abs(await nav.evaluate(el=>el.scrollTop)-before)<3,'desktop sidebar offset');
  };
  await navClick('Sign-in activity');await navClick('Administration changes');await navClick('Content Management');
  await page.screenshot({path:path.join(output,'desktop-groups-scroll.png'),fullPage:true});
  // A stored closed group containing the current page must open on arrival.
  await page.evaluate(()=>{
   const nav=document.getElementById('admin-nav');sessionStorage.setItem('santolan.admin-navigation.'+nav.dataset.scrollKey+'.desktop.groups',JSON.stringify({programs:false}));
  });
  await go('/programs/manage/');assert.equal(await programs.evaluate(el=>el.open),true);await current('programs');
  await page.setViewportSize({width:390,height:650});
  const menu=page.getByRole('button',{name:/Workspace menu/});await menu.click();await nav.locator('nav').waitFor();
  await page.waitForTimeout(350);
  const mobileLink=nav.getByRole('link',{name:'Sign-in activity',exact:true});await mobileLink.scrollIntoViewIfNeeded();
  const mobileOffset=await nav.evaluate(el=>el.scrollTop);assert.ok(mobileOffset>0);
  await mobileLink.click();await page.waitForLoadState('networkidle');
  await menu.click();await page.waitForTimeout(350);
  assert.ok(Math.abs(await nav.evaluate(el=>el.scrollTop)-mobileOffset)<3,'mobile sidebar offset');
  await nav.getByRole('link',{name:'Sign-in activity',exact:true}).focus();await page.keyboard.press('Escape');
  await page.waitForTimeout(350);assert.equal(await menu.getAttribute('aria-expanded'),'false');
  assert.equal(await menu.evaluate(el=>el===document.activeElement),true);
  await page.locator('.display-trigger').click();await page.locator('#display-size').selectOption('largest');
  await page.locator('[data-preference="contrast"]').check();await page.locator('.display-close').click();
  await page.setViewportSize({width:320,height:850});await menu.click();await page.waitForTimeout(350);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'largest text native mobile');
  await page.screenshot({path:path.join(output,'mobile-largest-groups.png'),fullPage:true});
  if(visualStage==='after'){
   await inspectAppearance();
   assert.equal(await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches),true);
   await page.screenshot({path:path.join(output,'mobile-largest-viewport.png')});
   await page.setViewportSize({width:1440,height:850});
   await inspectAppearance();
   await page.screenshot({path:path.join(output,'native-contrast.png')});
   await page.locator('.display-trigger').click();await page.locator('[data-preference="contrast"]').uncheck();
   await page.locator('#display-size').selectOption('default');await page.locator('.display-close').click();
   await inspectAppearance();
   await page.screenshot({path:path.join(output,'native-normal.png')});
  }
  const restricted=await browser.newPage({viewport:{width:390,height:850}});restricted.on('pageerror',e=>errors.push(e.message));
  await login(restricted,process.env.QA_ENCODER);
  assert.deepEqual(await restricted.locator('#admin-nav [data-module-label]').allTextContents(),['Dashboard','Members']);
  assert.equal(await restricted.locator('#admin-nav a[href="/admin/auth/user/"]').count(),0);
  for(const route of ['/admin/auth/user/','/admin/auth/group/','/programs/photos/','/announcements/manage/results/'])
   assert.equal((await restricted.goto(process.env.QA_URL+route)).status(),403);
  await restricted.goto(process.env.QA_URL+'/membership/applications/new/');
  assert.match(await restricted.locator('main').innerText(),/Birth Certificate OR Marriage Certificate/);
  await restricted.getByRole('button',{name:/Workspace menu/}).click();await restricted.waitForTimeout(350);
  await restricted.screenshot({path:path.join(output,'restricted-encoder-mobile.png'),fullPage:true});
  // Storage failures cannot prevent disclosure, navigation or native Admin rendering.
  const blocked=await browser.newContext({viewport:{width:1440,height:850}});
  await blocked.addInitScript(()=>Object.defineProperty(window,'sessionStorage',{get(){throw new Error('Synthetic blocked storage');}}));
  const fallback=await blocked.newPage(),blockedStorageErrors=[];
  fallback.on('pageerror',e=>blockedStorageErrors.push({message:e.message,stack:e.stack}));
  await login(fallback,process.env.QA_USERNAME);
  assert.deepEqual(await fallback.locator('#admin-nav [data-module-label]').allTextContents(),labels);
  const fallbackGroup=fallback.locator('#admin-nav [data-group-key="programs"]');
  await fallbackGroup.locator('summary').click();assert.equal(await fallbackGroup.evaluate(el=>el.open),false);
  await fallback.locator('#admin-nav').getByRole('link',{name:'Document types',exact:true}).click();await fallback.waitForLoadState('networkidle');
  assert.equal(await fallback.locator('#admin-nav [data-group-key="administration"]').getAttribute('data-current'),'true');
  await fallbackGroup.locator('summary').click();assert.equal(await fallbackGroup.evaluate(el=>el.open),false);
  // Django's unchanged native filters.js reads storage outside a guard. Its known
  // failure must not prevent our native-page navigation; report it explicitly.
  assert.equal(blockedStorageErrors.length,1);
  assert.equal(blockedStorageErrors[0].message,'Synthetic blocked storage');
  assert.match(blockedStorageErrors[0].stack,/admin\/js\/filters\.js/);
  await blocked.close();await restricted.close();
  assert.deepEqual(errors,[]);
  assert.deepEqual(consoleErrors,[]);
  const visualReport={stage:visualStage||null,minimumTextContrast:contrastChecks.length?Math.min(...contrastChecks.map(item=>item.ratio)):null};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify({visualReport,contrastChecks},null,2));
  console.log(JSON.stringify({result:'passed',modules:8,widths:[320,390,768,1024,1440],customAndNativeAdmin:true,restrictedStaff:true,keyboardDisclosure:true,persistedExpansion:true,desktopMobileScroll:true,storageFailure:true,blockedStorageNativeFilterErrors:blockedStorageErrors.length,largestTextAndContrast:true,ewafReportsHonest:true,javascriptErrors:0,consoleErrors:0,visualReport}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
