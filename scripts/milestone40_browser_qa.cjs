const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const publicContext=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage(),publicPage=await publicContext.newPage(),errors=[];
  for(const p of [page,publicPage]){
   p.on('pageerror',e=>errors.push(e.message));
   p.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url());});
  }
  const output=path.join(__dirname,'../.local/qa-milestone40');fs.mkdirSync(output,{recursive:true});
  const go=async(p,route)=>assert.equal((await p.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200,route);
  const noOverflow=async p=>assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Overflow: '+p.url()+' at '+p.viewportSize().width);
  const member='/members/'+process.env.QA_MEMBER_ID+'/';
  await go(page,'/accounts/login/');
  await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/dashboard/');
  await page.getByRole('link',{name:'Open member directory'}).click();
  await page.locator('#search').fill('BROWSER-40');await page.getByRole('button',{name:'Filter members'}).click();
  await page.getByRole('link',{name:'Sample Applicant',exact:true}).click();
  await page.getByRole('link',{name:'Edit member profile'}).click();
  await page.locator('#id_full_name').fill('Updated Browser Member');await page.locator('#id_notes').fill('Corrected the member name after review.');
  await page.getByRole('button',{name:'Save member changes'}).click();await page.waitForURL('**'+member);
  await page.getByRole('heading',{name:'Updated Browser Member',exact:true}).waitFor();
  for(const status of ['archived','active']){
   await page.locator('#id_status').selectOption(status);await page.locator('#id_notes').fill('Browser workflow status change.');
   await page.getByRole('button',{name:'Update status',exact:true}).click();await page.waitForLoadState('networkidle');
   assert.equal(await page.locator('#id_status').inputValue(),status);
  }
  await go(page,'/announcements/manage/new/');
  const title='Community information and association updates';
  await page.locator('#id_title').fill(title);await page.locator('#id_content').fill('A synthetic announcement for browser validation.\n\nInformation is readable without a member account.');
  await page.locator('#id_image').setInputFiles(process.env.QA_IMAGE);await page.locator('#id_image_alt').fill('A teal image used for browser validation.');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  await page.waitForURL(/\/announcements\/manage\/[0-9a-f-]+\/$/);
  const manage=new URL(page.url()).pathname,id=manage.split('/')[3],detail='/announcements/'+id+'/';
  assert.equal((await publicContext.request.get(process.env.QA_URL+detail)).status(),404);
  const transition=async action=>{
   await page.locator('#id_action').selectOption(action);await page.locator('#id_confirm').check();
   await page.getByRole('button',{name:'Apply publication change'}).click();await page.waitForLoadState('networkidle');
  };
  await transition('published');
  await go(publicPage,'/');await publicPage.getByRole('link',{name:title,exact:true}).click();
  await publicPage.getByRole('heading',{name:title,exact:true}).waitFor();
  assert.equal(await publicPage.locator('.nav-link.active').textContent(),'Announcements');
  assert(await publicPage.locator('.announcement-image').evaluate(e=>e.complete&&e.naturalWidth>0));
  const routes=[['/members/',page],[member,page],[member+'edit/',page],['/announcements/manage/',page],
   ['/announcements/manage/new/',page],[manage,page],[manage+'edit/',page],['/',publicPage],['/announcements/',publicPage],[detail,publicPage]];
  let checks=0;
  for(const width of [320,390,768,1024,1440]){
   for(const [route,p] of routes){
    await p.setViewportSize({width,height:900});await go(p,route);await noOverflow(p);checks++;
    const problems=await p.evaluate(()=>{
     const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
     return {duplicate:ids.filter((id,i)=>ids.indexOf(id)!==i),unlabelled:[...document.querySelectorAll('input:not([type=hidden]),textarea,select')].filter(e=>!e.labels.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).map(e=>e.id)};
    });
    assert.deepEqual(problems,{duplicate:[],unlabelled:[]});
    if([320,1440].includes(width)&&[member,manage,detail].includes(route))await p.screenshot({path:path.join(output,(route===member?'member':route===manage?'review':'public')+'-'+width+'.png'),fullPage:true});
   }
  }
  for(const [route,p] of routes){
   await p.setViewportSize({width:320,height:900});await go(p,route);
   await p.locator('.display-trigger').click();await p.locator('#display-size').selectOption('largest');await p.locator('.display-close').click();await noOverflow(p);
  }
  await page.setViewportSize({width:1440,height:1000});await go(page,member);
  await page.getByRole('button',{name:'Update status',exact:true}).focus();
  assert.equal(await page.getByRole('button',{name:'Update status',exact:true}).evaluate(e=>getComputedStyle(e).outlineWidth),'3px');
  await publicPage.emulateMedia({reducedMotion:'reduce'});await go(publicPage,'/');
  assert.equal(await publicPage.locator('[data-sculpture]').evaluate(e=>getComputedStyle(e).transform),'none');
  await go(page,manage+'edit/');await page.locator('#id_content').fill('Updated public notice.');
  await page.getByRole('button',{name:'Save changes',exact:true}).click();await page.waitForURL('**'+manage);
  await go(publicPage,detail);await publicPage.getByText('Updated public notice.',{exact:true}).waitFor();
  await transition('archived');assert.equal((await publicContext.request.get(process.env.QA_URL+detail)).status(),404);
  assert.equal((await publicContext.request.get(process.env.QA_URL+detail+'image/')).status(),404);
  await transition('published');await transition('deleted');
  assert.equal((await publicContext.request.get(process.env.QA_URL+detail)).status(),404);
  await go(page,'/announcements/manage/?status=deleted');await page.getByRole('link',{name:title,exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  const report={status:'pass',responsiveChecks:checks,enlargedTextChecks:routes.length,errors,
   workflows:['member search/edit/archive/restore/history','announcement draft/image/publish/edit/archive/republish/delete','public visibility','focus','reduced motion']};
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
