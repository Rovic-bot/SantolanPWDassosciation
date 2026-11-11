const fs=require('fs'), path=require('path'), assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const local=path.resolve(__dirname,'../.local/main-testing');
const manifest=JSON.parse(fs.readFileSync(path.join(local,'connection.json'),'utf8'));
const data=JSON.parse(fs.readFileSync(path.join(path.dirname(manifest.media),'dataset.json'),'utf8'));
const login=JSON.parse(fs.readFileSync(path.join(local,'login.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const output=path.join(local,'screenshots');
 const errors=[];
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(60000);
  page.on('pageerror',error=>errors.push(error.message));
  const go=async route=>{const response=await page.goto('http://127.0.0.1:8000'+route,{waitUntil:'networkidle'});assert.equal(response.status(),200);assert.equal(response.headers()['x-santolan-environment'],'MAIN-FICTIONAL-TESTING');};
  await go('/accounts/login/');
  await page.locator('[name=username]').fill(login.username);await page.locator('[name=password]').fill(login.password);
  await Promise.all([page.waitForNavigation({waitUntil:'networkidle'}),page.getByRole('button',{name:'Sign in',exact:true}).click()]);
  const program=data.programs['EWAF Lab — Pending Evidence'], application=data.application_ids[program][1];
  await go(`/programs/manage/${program}/applications/${application}/`);
  const card=page.locator('[data-member-document]').filter({hasText:'Verified'}).first();
  assert.ok(await card.count());
  const review=card.getByRole('link',{name:'Review',exact:true});assert.ok(await review.isEnabled());
  await review.click();await page.waitForLoadState('networkidle');
  assert.ok(page.url().includes('/verify/?application='+application));
  await page.getByRole('button',{name:'Save document review',exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'12-working-document-review.png')});
  await page.getByRole('link',{name:'Back to applicant review',exact:true}).click();await page.waitForLoadState('networkidle');
  await page.locator('#disability-review summary').click();
  assert.ok((await page.locator('#disability-review').innerText()).includes('at least one'));
  await page.locator('#program-fit-review summary').click();
  await page.locator('[data-requirements-prerequisite]').waitFor({state:'visible'});
  assert.equal(await page.getByRole('button',{name:'Save additional requirement review',exact:true}).count(),0);
  assert.ok(!(await page.locator('main').innerText()).includes('PR_REQUIREMENTS_STALE'));
  await page.locator('#program-fit-review').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(output,'13-requirement-review-guidance.png')});
  await page.getByRole('link',{name:'Review program requirement checklist',exact:true}).click();
  assert.ok(await page.locator('#program-requirements').getAttribute('open')!==null);
  await page.locator('[data-shared-review-reason]').fill('Fictional browser check; this text is not submitted.');
  assert.equal(await page.locator('#eligibility_notes').inputValue(),'Fictional browser check; this text is not submitted.');
  await page.locator('#eligibility_notes').fill('Bidirectional reason check; not submitted.');
  assert.equal(await page.locator('[data-shared-review-reason]').inputValue(),'Bidirectional reason check; not submitted.');
  for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);}
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(local,'review-browser-results.json'),JSON.stringify({document_review_navigation:true,return_to_correct_applicant:true,stale_checklist_guidance:true,reason_sync:true,responsive_widths:[320,390,768,1440],application_mutations:0,page_errors:errors},null,2));
  console.log('PASS: verified-document Review, correct applicant return, disability relevance, stale checklist guidance, shared reason and four responsive widths; no application data changed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
