const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 try {
  const routes=JSON.parse(process.env.QA_ROUTES),profile=JSON.parse(process.env.QA_PROFILE),errors=[];
  const admin=await browser.newContext({viewport:{width:1440,height:1000}}),visitor=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await admin.newPage(),publicPage=await visitor.newPage();
  for(const p of [page,publicPage]){p.on('pageerror',e=>errors.push(e.message));p.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+new URL(r.url()).pathname);});}
  const out=path.join(__dirname,'../.local/workflow-alignment-20260929/browser');fs.mkdirSync(out,{recursive:true});
  const go=async(p,route)=>assert.equal((await p.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200,route);
  let checks=0;
  const responsive=async(p,name)=>{
   for(const width of [320,390,768,1440]){
    await p.setViewportSize({width,height:950});
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Overflow '+name+' '+width);checks++;
   }
   await p.screenshot({path:path.join(out,name+'-desktop.png'),fullPage:true});
   await p.setViewportSize({width:390,height:844});
   await p.locator('.display-trigger').click();await p.locator('#display-size').selectOption('largest');await p.locator('.display-close').click();
   assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Enlarged overflow '+name);checks++;
   await p.screenshot({path:path.join(out,name+'-mobile.png'),fullPage:true});
   await p.locator('.display-trigger').click();await p.locator('#display-size').selectOption('default');await p.locator('.display-close').click();
   await p.setViewportSize({width:1440,height:1000});
  };
  await go(publicPage,'/membership/register/');await publicPage.getByText('Synthetic onsite requirement',{exact:true}).waitFor();
  assert.equal(await publicPage.locator('main form').count(),0);await responsive(publicPage,'guidelines');
  await go(publicPage,routes.event);await publicPage.getByText('Open to everyone',{exact:true}).waitFor();assert.equal(await publicPage.locator('a[href$="/register/"]').filter({hasText:'Register'}).count(),0);
  await go(publicPage,routes.program);await publicPage.getByRole('link',{name:'Apply for this program'}).click();
  for(const [key,value] of Object.entries({control_number:process.env.QA_CONTROL,full_name:'John Doe',birthdate:profile.birthdate,contact_number:profile.contact_number}))await publicPage.locator('#id_'+key).fill(value);
  await publicPage.getByRole('button',{name:'Verify and continue'}).click();await publicPage.waitForURL('**/apply/');
  await publicPage.getByRole('button',{name:'Submit application',exact:true}).click();await publicPage.waitForURL('**/programs/status/**/');
  await publicPage.getByText('Under Review',{exact:true}).waitFor();
  const qr=publicPage.getByAltText('QR code linking to this application status page');await qr.waitFor();assert.ok(await qr.evaluate(img=>img.complete&&img.naturalWidth>0));
  assert.equal(await publicPage.getByText('John Doe',{exact:true}).count(),0);await responsive(publicPage,'status');
  await go(page,'/accounts/login/');await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/dashboard/');
  await go(page,routes.encode);await responsive(page,'onsite');
  for(const [key,value] of Object.entries({...profile,control_number:'BROWSER-ONSITE'}))await page.locator('#id_'+key).fill(String(value));
  await page.locator('#id_disability_type').selectOption(process.env.QA_DISABILITY);
  await page.getByRole('button',{name:'Save onsite registration for review'}).click();await page.waitForURL('**/membership/applications/*/');
  await go(page,routes.edit);assert.ok(await page.locator('input[name="eligible_disability_types"]:checked').count());await responsive(page,'program-types');
  await go(page,routes.ranking);await responsive(page,'ranking');
  const selection=page.locator('form').filter({has:page.getByRole('button',{name:'Select and approve'})});
  await selection.locator('textarea[name="notes"]').fill('Reviewed evidence and the ranked applicant list.');await selection.locator('input[name="confirm"]').check();await selection.getByRole('button',{name:'Select and approve'}).click();await page.waitForLoadState('networkidle');
  await page.getByText('Approved',{exact:true}).waitFor();
  await go(publicPage,routes.status);await publicPage.getByText('Approved',{exact:true}).waitFor();
  await go(publicPage,routes.announcement);await publicPage.getByText('J**n D.',{exact:true}).waitFor();await publicPage.getByText('Approved',{exact:true}).waitFor();assert.equal(await publicPage.getByText('John Doe',{exact:true}).count(),0);await responsive(publicPage,'announcement');
  assert.deepEqual(errors,[]);console.log(JSON.stringify({responsiveChecks:checks,browserErrors:errors.length,workflows:'onsite, public application/status/QR, explicit ranking selection, original announcement results'}));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
