const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 try {
  const admin=await browser.newContext({viewport:{width:1440,height:1000}}),visitor=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await admin.newPage(),publicPage=await visitor.newPage(),errors=[];
  for(const p of [page,publicPage]){
   p.on('pageerror',e=>errors.push(e.message));
   p.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url());});
  }
  const output=path.join(__dirname,'../.local/qa-milestone50');fs.mkdirSync(output,{recursive:true});
  const go=async(p,route)=>assert.equal((await p.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200,route);
  const noOverflow=async p=>assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Overflow: '+p.url()+' at '+p.viewportSize().width);
  await go(page,'/accounts/login/');
  await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/dashboard/');
  await page.getByRole('link',{name:'Manage events',exact:true}).click();await page.getByRole('link',{name:'Create event',exact:true}).click();
  const title='Community gathering and accessible activities';
  await page.locator('#id_title').fill(title);await page.locator('#id_description').fill('A synthetic community event for browser validation.\n\nAll essential arrangements are available in text.');
  await page.locator('#id_location').fill('Synthetic community venue');await page.locator('#id_capacity').fill('2');
  for(const [name,value] of Object.entries(JSON.parse(process.env.QA_SCHEDULE)))await page.locator('#id_'+name).fill(value);
  await page.locator('#id_image').setInputFiles(process.env.QA_IMAGE);await page.locator('#id_image_alt').fill('Teal event illustration used for testing.');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.waitForURL(/\/events\/manage\/[0-9a-f-]+\/$/);
  const manage=new URL(page.url()).pathname,id=manage.split('/')[3],detail='/events/'+id+'/',register=detail+'register/';
  assert.equal((await visitor.request.get(process.env.QA_URL+detail)).status(),404);
  const publication=async action=>{
   await go(page,manage);await page.locator('#id_action').selectOption(action);await page.locator('#id_notes').fill('Reviewed event publication change.');await page.locator('#id_confirm').check();
   await page.getByRole('button',{name:'Apply event change'}).click();await page.waitForLoadState('networkidle');
  };
  await publication('published');await go(publicPage,'/');await publicPage.getByRole('link',{name:title,exact:true}).click();
  assert.equal(await publicPage.locator('.nav-link.active').textContent(),'Events');
  assert(await publicPage.locator('.announcement-image').evaluate(e=>e.complete&&e.naturalWidth>0));
  await publicPage.getByRole('link',{name:'Register for this event'}).click();
  await publicPage.locator('#id_control_number').fill('BROWSER-50');await publicPage.locator('#id_full_name').fill('Wrong name');
  await publicPage.locator('#id_birthdate').fill(process.env.QA_BIRTHDATE);await publicPage.locator('#id_contact_number').fill('+63 (917) 123-4567');
  await publicPage.getByRole('button',{name:'Verify and register'}).click();await publicPage.getByText('Member verification failed.',{exact:false}).waitFor();
  await publicPage.locator('#id_full_name').fill('  SAMPLE   applicant ');await publicPage.getByRole('button',{name:'Verify and register'}).click();
  await publicPage.waitForURL('**'+detail+'registered/');await publicPage.getByRole('heading',{name:'Registration recorded.'}).waitFor();
  assert.equal(await publicPage.getByText('BROWSER-50',{exact:true}).count(),0);
  await go(page,manage+'registrations/');await page.getByRole('link',{name:'Sample Applicant',exact:true}).click();
  const attendance=new URL(page.url()).pathname;
  const participation=async status=>{
   await page.locator('#id_status').selectOption(status);await page.locator('#id_notes').fill('Reviewed participation change.');
   await page.getByRole('button',{name:'Update registration',exact:true}).click();await page.waitForLoadState('networkidle');
   assert.equal(await page.locator('#id_status').inputValue(),status);
  };
  await participation('confirmed');await participation('cancelled');await participation('registered');
  const routes=[['/',publicPage],['/events/',publicPage],[detail,publicPage],[register,publicPage],[detail+'registered/',publicPage],
   ['/events/manage/',page],['/events/manage/new/',page],[manage,page],[manage+'edit/',page],[manage+'registrations/',page],[attendance,page],['/members/'+process.env.QA_MEMBER_ID+'/',page]];
  let checks=0;
  for(const width of [320,390,768,1024,1440]){
   for(const [route,p] of routes){
    await p.setViewportSize({width,height:900});await go(p,route);await noOverflow(p);checks++;
    const problems=await p.evaluate(()=>{
     const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
     return {duplicate:ids.filter((id,i)=>ids.indexOf(id)!==i),unlabelled:[...document.querySelectorAll('input:not([type=hidden]),textarea,select')].filter(e=>!e.labels.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).map(e=>e.id)};
    });assert.deepEqual(problems,{duplicate:[],unlabelled:[]});
    if([320,1440].includes(width)&&[detail,manage,attendance,register].includes(route))await p.screenshot({path:path.join(output,(route===detail?'public':route===manage?'review':route===attendance?'attendance':'register')+'-'+width+'.png'),fullPage:true});
   }
  }
  for(const [route,p] of routes){
   await p.setViewportSize({width:320,height:900});await go(p,route);
   await p.locator('.display-trigger').click();await p.locator('#display-size').selectOption('largest');await p.locator('.display-close').click();await noOverflow(p);
  }
  await page.setViewportSize({width:1440,height:1000});await go(page,attendance);
  await page.getByRole('button',{name:'Update registration',exact:true}).focus();
  assert.equal(await page.getByRole('button',{name:'Update registration',exact:true}).evaluate(e=>getComputedStyle(e).outlineWidth),'3px');
  await publicPage.emulateMedia({reducedMotion:'reduce'});await go(publicPage,'/');
  assert.equal(await publicPage.locator('[data-sculpture]').evaluate(e=>getComputedStyle(e).transform),'none');
  await go(page,manage+'edit/');for(const [name,value] of Object.entries(JSON.parse(process.env.QA_PAST_SCHEDULE)))await page.locator('#id_'+name).fill(value);
  await page.locator('#id_notes').fill('Move the synthetic fixture into the past to exercise attendance.');
  await page.getByRole('button',{name:'Save changes',exact:true}).click();await page.waitForURL('**'+manage);
  await go(page,attendance);await participation('attended');
  await go(publicPage,'/events/?period=past');await publicPage.getByRole('link',{name:title,exact:true}).waitFor();
  await go(page,'/members/'+process.env.QA_MEMBER_ID+'/');await page.getByRole('link',{name:title,exact:true}).waitFor();
  await publication('cancelled');await go(publicPage,detail);await publicPage.getByText('This event has been cancelled.',{exact:true}).waitFor();
  await publication('archived');assert.equal((await visitor.request.get(process.env.QA_URL+detail)).status(),404);
  assert.equal((await visitor.request.get(process.env.QA_URL+detail+'image/')).status(),404);
  assert.deepEqual(errors,[]);
  const report={status:'pass',responsiveChecks:checks,enlargedTextChecks:routes.length,errors,
   workflows:['event draft/image/publish/edit/cancel/archive','four-field failure and normalized success','session receipt','registration confirm/cancel/restore/attendance','member history','past events','focus','reduced motion']};
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
