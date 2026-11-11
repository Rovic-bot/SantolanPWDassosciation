const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 try {
  const admin=await browser.newContext({viewport:{width:1440,height:1000}}),visitor=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await admin.newPage(),publicPage=await visitor.newPage(),errors=[];
  for(const p of [page,publicPage]){p.on('pageerror',e=>errors.push(e.message));p.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url());});}
  const output=path.join(__dirname,'../.local/qa-milestone60');fs.mkdirSync(output,{recursive:true});
  const go=async(p,route)=>assert.equal((await p.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200,route);
  const noOverflow=async p=>assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Overflow: '+p.url()+' at '+p.viewportSize().width);
  await go(page,'/accounts/login/');await page.locator('#id_username').fill(process.env.QA_USERNAME);await page.locator('#id_password').fill(process.env.QA_PASSWORD);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/dashboard/');
  await page.getByRole('link',{name:'Manage programs',exact:true}).click();await page.getByRole('link',{name:'Create program',exact:true}).click();
  const title='Community assistance and accessible support';
  await page.locator('#id_name').fill(title);await page.locator('#id_description').fill('A synthetic assistance program used for browser validation.');
  await page.locator('#id_assistance_type').fill('Association-defined support');await page.locator('#id_slots').fill('1');
  await page.locator('#id_budget').fill('9876543');await page.locator('#id_amount').fill('1000');
  await page.locator('#id_benefit').fill('Synthetic benefit description');await page.locator('#id_requirements').fill('Read the instructions and provide the requested documents.');
  for(const [name,value] of Object.entries(JSON.parse(process.env.QA_SCHEDULE)))await page.locator('#id_'+name).fill(value);
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.waitForURL(/\/programs\/manage\/[0-9a-f-]+\/$/);
  const manage=new URL(page.url()).pathname,id=manage.split('/')[3],detail='/programs/'+id+'/',verify=detail+'verify/',apply=detail+'apply/';
  assert.equal((await visitor.request.get(process.env.QA_URL+detail)).status(),404);
  for(const [kind,label,instructions] of [['document','Supporting proof','Upload the requested proof.'],['text','Explain your request','Describe the requested support.'],['acknowledgement','I have read the requirements','Confirm you have read the instructions.']]){
   await page.getByRole('link',{name:'Add requirement',exact:true}).click();await page.locator('#id_label').fill(label);await page.locator('#id_kind').selectOption(kind);
   await page.locator('#id_instructions').fill(instructions);await page.locator('#id_notes').fill('Configure the synthetic requirement.');
   await page.getByRole('button',{name:'Save requirement',exact:true}).click();await page.waitForURL('**'+manage);
  }
  const requirementEdit=new URL(await page.getByRole('link',{name:'Edit Supporting proof',exact:true}).getAttribute('href'),process.env.QA_URL).pathname;
  const publication=async action=>{
   await go(page,manage);await page.locator('#id_action').selectOption(action);await page.locator('#id_notes').fill('Reviewed program publication change.');await page.locator('#id_confirm').check();
   await page.getByRole('button',{name:'Apply program change'}).click();await page.waitForLoadState('networkidle');
  };
  await publication('published');await go(publicPage,'/programs/');await publicPage.getByRole('link',{name:title,exact:true}).click();
  assert.equal(await publicPage.locator('.nav-link.active').textContent(),'Programs');
  assert.equal(await publicPage.getByText('9876543',{exact:false}).count(),0);
  await publicPage.getByRole('link',{name:'Apply for this program'}).click();
  const verifyMember=async name=>{
   await publicPage.locator('#id_control_number').fill('BROWSER-60');await publicPage.locator('#id_full_name').fill(name);
   await publicPage.locator('#id_birthdate').fill(process.env.QA_BIRTHDATE);await publicPage.locator('#id_contact_number').fill('+63 (917) 000-0000');
   await publicPage.getByRole('button',{name:'Verify and continue'}).click();
  };
  await verifyMember('Wrong name');await publicPage.getByText('Member verification failed.',{exact:false}).waitFor();
  await verifyMember('  SAMPLE   applicant ');await publicPage.waitForURL('**'+apply);
  assert.equal(await publicPage.getByText('Sample Applicant',{exact:true}).count(),0);
  // Exercise the private application form before submission consumes the verification grant.
  for(const width of [320,390,768,1024,1440]){await publicPage.setViewportSize({width,height:900});await noOverflow(publicPage);}
  await publicPage.screenshot({path:path.join(output,'application-desktop.png'),fullPage:true});
  await publicPage.setViewportSize({width:320,height:900});
  await publicPage.locator('.display-trigger').click();await publicPage.locator('#display-size').selectOption('largest');await publicPage.locator('.display-close').click();await noOverflow(publicPage);
  await publicPage.screenshot({path:path.join(output,'application-mobile-largest.png'),fullPage:true});
  await publicPage.locator('.display-trigger').click();await publicPage.locator('#display-size').selectOption('default');await publicPage.locator('.display-close').click();
  await publicPage.setViewportSize({width:1440,height:1000});
  await publicPage.getByLabel(/^Supporting proof/).setInputFiles(process.env.QA_DOCUMENT);
  await publicPage.getByLabel(/^Explain your request/).fill('Private synthetic application answer.');
  await publicPage.getByLabel('I have read the requirements',{exact:true}).check();
  await publicPage.getByRole('button',{name:'Submit application',exact:true}).click();await publicPage.waitForURL('**'+detail+'submitted/');
  await publicPage.getByRole('heading',{name:'Application recorded.'}).waitFor();
  assert.equal(await publicPage.getByText('BROWSER-60',{exact:true}).count(),0);
  await go(page,manage+'applications/');await page.getByRole('link',{name:'Sample Applicant',exact:true}).click();
  const application=new URL(page.url()).pathname;
  const update=async status=>{await page.locator('#id_status').selectOption(status);await page.locator('#id_notes').fill('Reviewed application change.');await page.getByRole('button',{name:'Update application',exact:true}).click();await page.waitForLoadState('networkidle');assert.equal(await page.locator('#id_status').inputValue(),status);};
  await update('under_review');await update('cancelled');await update('under_review');
  const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:'Supporting proof — download',exact:true}).click();const download=await downloadPromise;
  assert.equal(await download.failure(),null);
  await page.getByText('Private synthetic application answer.',{exact:true}).waitFor();
  await go(page,requirementEdit);await page.locator('#id_label').fill('Updated supporting proof');await page.locator('#id_notes').fill('Change requirements for future applications.');await page.getByRole('button',{name:'Save requirement'}).click();await page.waitForURL('**'+manage);
  await go(page,application);await page.getByRole('link',{name:'Supporting proof — download',exact:true}).waitFor();
  await go(page,'/members/'+process.env.QA_MEMBER_ID+'/');await page.getByRole('link',{name:title,exact:true}).waitFor();
  const routes=[['/',publicPage],['/programs/',publicPage],['/programs/?period=past',publicPage],[detail,publicPage],[verify,publicPage],[detail+'submitted/',publicPage],
   ['/programs/manage/',page],['/programs/manage/new/',page],[manage,page],[manage+'edit/',page],[manage+'requirements/new/',page],[requirementEdit,page],[manage+'applications/',page],[application,page],['/members/'+process.env.QA_MEMBER_ID+'/',page]];
  let checks=5;
  for(const width of [320,390,768,1024,1440])for(const [route,p] of routes){
   await p.setViewportSize({width,height:900});await go(p,route);await noOverflow(p);checks++;
   const problems=await p.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return {duplicate:ids.filter((id,i)=>ids.indexOf(id)!==i),unlabelled:[...document.querySelectorAll('input:not([type=hidden]),textarea,select')].filter(e=>!e.labels.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).map(e=>e.id)};});
   assert.deepEqual(problems,{duplicate:[],unlabelled:[]});
   if([320,1440].includes(width)&&[detail,manage,application].includes(route))await p.screenshot({path:path.join(output,(route===detail?'public':route===manage?'review':'application-review')+'-'+width+'.png'),fullPage:true});
  }
  for(const [route,p] of routes){await p.setViewportSize({width:320,height:900});await go(p,route);await p.locator('.display-trigger').click();await p.locator('#display-size').selectOption('largest');await p.locator('.display-close').click();await noOverflow(p);}
  await page.setViewportSize({width:1440,height:1000});await go(page,application);await page.getByRole('button',{name:'Update application',exact:true}).focus();
  assert.equal(await page.getByRole('button',{name:'Update application',exact:true}).evaluate(e=>getComputedStyle(e).outlineWidth),'3px');
  await publicPage.emulateMedia({reducedMotion:'reduce'});await go(publicPage,'/');assert.equal(await publicPage.locator('[data-sculpture]').evaluate(e=>getComputedStyle(e).transform),'none');
  await publication('cancelled');await go(publicPage,detail);await publicPage.getByText('This program has been cancelled.',{exact:true}).waitFor();
  await publication('archived');assert.equal((await visitor.request.get(process.env.QA_URL+detail)).status(),404);
  assert.deepEqual(errors,[]);
  const report={status:'pass',responsiveChecks:checks,enlargedTextChecks:routes.length+1,errors,workflows:['draft/configure/publish/cancel/archive','two-step verification and private upload','session receipt','review/cancel/restore','audited attachment download','retained requirement snapshot','member history','focus','reduced motion']};
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
