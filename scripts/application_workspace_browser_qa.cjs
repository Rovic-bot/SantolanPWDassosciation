const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base=process.env.QA_URL, url=base+process.env.QA_PORTFOLIO_ROUTE, output=process.env.QA_OUTPUT;
  const cookie={name:'sessionid',value:process.env.QA_ADMIN_SESSION,url:base};
  const errors=[], writes=[], layouts=[];
  try {
    const context=await browser.newContext({viewport:{width:1600,height:1000},reducedMotion:'reduce',colorScheme:'dark'});
    await context.addCookies([cookie]);
    await context.route(base+'/**',route=>{if(route.request().method()!=='GET'){writes.push(route.request().method());return route.abort();}return route.continue();});
    const page=await context.newPage(); page.on('pageerror',error=>errors.push(error.message));
    let documents=0;
    page.on('request',request=>{if(request.isNavigationRequest() && request.frame()===page.mainFrame())documents++;});
    await page.goto(url);
    assert.equal(await page.locator('[data-review-submit]').isVisible(),false);
    assert.equal(await page.locator('[data-review-count]').textContent(),'8');
    assert.equal(await page.locator('a[aria-current=page]').textContent(),'Program Applications & Eligibility');
    assert.equal(await page.locator('[data-preview-name]').textContent(),'Medical Access Week');
    const select=name=>page.locator('[data-program-card]').filter({has:page.getByRole('heading',{name,exact:true})}).locator('[data-select-program]');
    const before=documents;
    await select('Assistive Device Distribution').click();
    assert.equal(await page.locator('[data-preview-name]').textContent(),'Assistive Device Distribution');
    assert.equal(await page.locator('[data-preview-applications]').textContent(),'3');
    assert.equal(await select('Assistive Device Distribution').getAttribute('aria-pressed'),'true');
    await select('Nutrition Support Batch 4').focus(); await page.keyboard.press('Space');
    assert.equal(await page.locator('[data-preview-name]').textContent(),'Nutrition Support Batch 4');
    assert.equal(await page.locator('[data-preview-disabled]').isVisible(),true);
    assert.equal(await page.locator('[data-preview-disabled]').isDisabled(),true);
    assert.equal(await page.locator('[data-preview-review]').isVisible(),false);
    await select('Financial Assistance Q4').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('[data-preview-name]').textContent(),'Financial Assistance Q4');
    assert.match(await page.locator('[data-preview-demand]').textContent(),/120%/);
    assert.equal(await page.locator('[data-preview-ring]').getAttribute('stroke-dasharray'),'100 100');
    const reviewUrl=await page.locator('[data-preview-review]').getAttribute('href');
    const selected=JSON.parse(await page.locator('#application-program-data').textContent()).find(item=>item.name==='Financial Assistance Q4');
    assert.equal(reviewUrl,selected.review_url);
    assert.equal(documents,before);
    const search=page.locator('#review-search'), type=page.locator('#review-type'), status=page.locator('#review-status');
    const settled=async(query,category,state,count)=>page.waitForFunction(({query,category,state,count})=>{
      const params=new URL(location.href).searchParams, results=document.querySelector('[data-review-results]');
      return (params.get('q')||'')===query && (params.get('assistance_type')||'')===category && (params.get('status')||'')===state &&
        results?.getAttribute('aria-busy')!=='true' && Number(results?.dataset.resultCount)===count;
    },{query,category,state,count});
    const reset=async()=>{await page.locator('form [data-review-reset]').click();await settled('','','',8);};
    await search.fill('Medical'); await settled('Medical','','',1);
    assert.equal(await page.locator('[data-preview-name]').textContent(),'Medical Access Week');
    assert.equal(await search.evaluate(node=>node===document.activeElement),true);
    await search.fill(process.env.QA_FIRST_CODE);await settled(process.env.QA_FIRST_CODE,'','',1);
    await search.fill('Unknown title'); await settled('Unknown title','','',0);
    assert.equal(await page.getByRole('heading',{name:'No programs found'}).isVisible(),true);
    assert.equal(await page.locator('[data-program-preview]').count(),0);
    await reset();
    await select('Family Caregiver Forum').click();
    await type.selectOption('Community');await settled('','Community','',2);
    assert.equal(await page.locator('[data-preview-name]').textContent(),'Family Caregiver Forum');
    await status.selectOption('draft');await settled('','Community','draft',1);
    assert.equal(await page.locator('[data-preview-disabled]').isDisabled(),true);
    await reset();await status.selectOption('closed');await settled('','','closed',1);
    assert.equal(await page.locator('.chooser-card .chooser-status').textContent(),'Published');
    await reset();
    await page.locator('form details summary').click();
    await page.locator('[name=with_applications]').check();await settled('','','',6);
    await page.locator('[name=registration]').selectOption('open');await settled('','','',5);
    await reset();await page.locator('form details summary').click();
    // Older fetches cannot replace a newer filter or reset.
    await page.route('**/admin/applications?**',async route=>{if(new URL(route.request().url()).searchParams.get('q')==='Medical')await new Promise(resolve=>setTimeout(resolve,600));return route.continue();});
    const requested=page.waitForRequest(request=>new URL(request.url()).searchParams.get('q')==='Medical');
    await search.fill('Medical');await requested;await search.fill('Digital');await settled('Digital','','',1);
    await page.waitForTimeout(700);assert.equal(await page.locator('[data-preview-name]').textContent(),'Digital Skills Workshop');
    await page.unroute('**/admin/applications?**');await reset();
    // IME input waits for committed text.
    await search.dispatchEvent('compositionstart');await search.fill('Medical');await page.waitForTimeout(400);
    assert.equal(await page.locator('[data-review-count]').textContent(),'8');
    await search.dispatchEvent('compositionend');await settled('Medical','','',1);await reset();
    await page.route('**/admin/applications?**',route=>route.abort());
    await search.fill('Unknown');await page.waitForFunction(()=>document.querySelector('[data-review-feedback]').textContent.includes('Could not'));
    assert.equal(await page.locator('.chooser-card').count(),8);
    await page.unroute('**/admin/applications?**');await reset();
    assert.equal(documents,before);
    // Selection is reflected in the URL and can be restored through browser history.
    await select('Assistive Device Distribution').click();
    const restoreUrl=page.url();
    await page.evaluate(()=>history.pushState({},'',location.pathname+'?q=Medical'));
    await page.goBack();await page.waitForFunction(()=>document.querySelector('[data-preview-name]')?.textContent==='Assistive Device Distribution');
    assert.equal(page.url(),restoreUrl);
    for(const theme of ['dark','light']) {
      if(await page.locator('html').getAttribute('data-dashboard-theme')!==theme)await page.locator('[data-dashboard-theme-toggle]').click();
      for(const width of [1600,1440,1280,1024,768,390,320]) {
        await page.setViewportSize({width,height:1000});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,`${theme}/${width}: overflow`);
        assert.deepEqual(await page.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(node=>node.id);return ids.filter((id,i)=>ids.indexOf(id)!==i);}),[]);
        const board=await page.locator('.chooser-board').boundingBox(),panel=await page.locator('.chooser-selected').boundingBox();
        if(width>=1280)assert.ok(panel.x>board.x+board.width,`${theme}/${width}: preview on right`);
        else assert.ok(panel.y>=board.y+board.height,`${theme}/${width}: preview below grid`);
        layouts.push({theme,width});
        if([1600,390].includes(width)) {
          await page.evaluate(async()=>{for(let y=0;y<document.documentElement.scrollHeight;y+=innerHeight){scrollTo({top:y,behavior:'instant'});await new Promise(requestAnimationFrame);}scrollTo({top:0,behavior:'instant'});});
          await page.screenshot({path:path.join(output,`applications-${theme}-${width}.png`),fullPage:true});
        }
      }
      await page.setViewportSize({width:1440,height:1000});await page.locator('.chooser-board').evaluate(node=>scrollTo({top:node.getBoundingClientRect().top+scrollY-100,behavior:'instant'}));
      const panel=await page.locator('.chooser-selected').boundingBox();assert.ok(panel.y>=76 && panel.y+panel.height<=1000);
      await page.screenshot({path:path.join(output,`applications-sticky-${theme}.png`)});
    }
    await page.setViewportSize({width:390,height:1000});
    await page.evaluate(()=>{document.documentElement.dataset.text='largest';document.documentElement.dataset.contrast='true';});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    await page.emulateMedia({forcedColors:'active'});await select('Medical Access Week').click();
    assert.equal(await page.locator('[data-preview-name]').isVisible(),true);
    await page.emulateMedia({forcedColors:'none'});
    await page.evaluate(()=>{delete document.documentElement.dataset.text;delete document.documentElement.dataset.contrast;});
    const expected=await page.locator('[data-preview-review]').getAttribute('href');
    await page.locator('[data-preview-review]').click();
    assert.equal(new URL(page.url()).pathname,expected);
    assert.equal(await page.locator('.content-section > .eyebrow').textContent(),'Medical Access Week');
    await page.goto(url);
    const card = page.locator('[data-program-card]').filter({has:page.getByRole('heading',{name:'Assistive Device Distribution',exact:true})});
    const cardReview = card.locator('[data-review-program]');
    const cardReviewUrl = await cardReview.getAttribute('href');
    await cardReview.click();
    await page.waitForURL(base + cardReviewUrl);
    assert.equal(await page.locator('.content-section > .eyebrow').textContent(),'Assistive Device Distribution');
    const nojs=await browser.newContext({javaScriptEnabled:false});await nojs.addCookies([cookie]);
    const fallback=await nojs.newPage();await fallback.goto(url);
    assert.equal(await fallback.locator('[data-review-submit]').isVisible(),true);
    const choice=fallback.locator('.chooser-card').filter({has:fallback.getByRole('heading',{name:'Nutrition Support Batch 4'})}).locator('[data-select-program]');
    await choice.click();assert.equal(await fallback.locator('[data-preview-name]').textContent(),'Nutrition Support Batch 4');
    assert.equal(await fallback.locator('[data-preview-disabled]').isDisabled(),true);await nojs.close();
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({layouts,errors,writes,checks:'Program-first selection, mouse/keyboard, zero-applicant review disabled, program-specific review links, over-capacity, immediate filters, empty state, selection retained, race cancellation, IME, retry, history, both themes, sticky preview, mobile, high contrast, native fallback'},null,2));
    console.log(`PASS: ${layouts.length} responsive layouts; program selection, automatic filters, private review links; no writes.`);
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
