/* No real application references: launched by the disposable Django test. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const origin=process.env.QA_URL;
if(!origin || !process.env.QA_REFERENCE || !process.env.QA_PROGRAM_URL) throw new Error('Synthetic test environment required');
const output='docs/public-tracking-popup-2026-11-08';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    fs.mkdirSync(output,{recursive:true});
    const page=await browser.newPage({viewport:{width:1440,height:960}}), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(origin+'/resources/');
    const trigger=page.locator('[data-tracking-open]'), dialog=page.locator('[data-tracking-dialog]');
    assert.equal(await page.locator('script[src*="public-concern-dialog.js"]').count(),1);
    await trigger.scrollIntoViewIfNeeded();
    const initialURL=page.url(), startY=await page.evaluate(()=>scrollY);
    await trigger.click();
    await dialog.locator('#id_reference').waitFor();
    assert.equal(page.url(),initialURL);
    assert(await dialog.evaluate(el=>el.contains(document.activeElement)));
    await dialog.screenshot({path:`${output}/verification-1440.png`});
    await dialog.locator('#id_reference').fill('SPA-NOT-ISSUED');
    await dialog.getByRole('button',{name:'View application status',exact:true}).click();
    await dialog.locator('.errorlist').first().waitFor();
    assert.equal(await dialog.locator('[role=status]').textContent(),'Please review the form errors.');
    assert(!(await dialog.textContent()).includes('Synthetic popup program'));
    await dialog.locator('#id_reference').fill(process.env.QA_REFERENCE);
    await dialog.getByRole('button',{name:'View application status',exact:true}).click();
    await dialog.getByRole('heading',{name:'Application progress',exact:true}).waitFor();
    assert.equal(page.url(),initialURL);
    assert(await dialog.getByRole('heading',{name:'Received',exact:true}).isVisible());
    for(const secret of ['PRIVATE-APPLICATION-ANSWER','PRIVATE-ASSESSMENT-NOTE',process.env.QA_MEMBER,process.env.QA_CONTROL]) {
      assert(!(await dialog.textContent()).includes(secret));
    }
    await dialog.screenshot({path:`${output}/synthetic-progress-1440.png`});
    const progressURL=await dialog.getByRole('link',{name:'Refresh progress'}).getAttribute('href');
    const refreshed=page.waitForResponse(r=>r.url()===origin+progressURL && r.request().method()==='GET');
    await dialog.getByRole('link',{name:'Refresh progress'}).click();
    const response=await refreshed;
    assert.match(response.headers()['cache-control'],/no-store/);
    await page.waitForFunction(()=>!document.querySelector('[data-tracking-dialog] [data-concern-body]').hasAttribute('aria-busy'));
    assert.equal(page.url(),initialURL);
    for(const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
      await dialog.screenshot({path:`${output}/synthetic-progress-${width}.png`});
    }
    await page.setViewportSize({width:1440,height:960});
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(),false);
    assert.equal(await dialog.locator('[data-concern-body]').textContent(),'');
    assert(await trigger.evaluate(el=>el===document.activeElement));
    assert(Math.abs(await page.evaluate(()=>scrollY)-startY)<2);
    await trigger.click();
    await dialog.locator('#id_reference').waitFor();
    assert.equal(await dialog.locator('#id_reference').inputValue(),'');
    await dialog.locator('#id_reference').fill(process.env.QA_REFERENCE);
    await dialog.getByRole('button',{name:'View application status',exact:true}).click();
    await dialog.getByRole('button',{name:'Finish tracking',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('[data-tracking-dialog]').open);
    const finished=await page.request.get(origin+progressURL);
    assert(new URL(finished.url()).pathname.endsWith('/tracking/'));
    assert.equal(page.url(),initialURL);
    await page.route('**/programs/tracking/',route=>route.abort());
    await trigger.click();
    await dialog.getByRole('button',{name:'Try again',exact:true}).waitFor();
    await page.unroute('**/programs/tracking/');
    await dialog.getByRole('button',{name:'Try again',exact:true}).click();
    await dialog.locator('#id_reference').waitFor();
    for(const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await dialog.screenshot({path:`${output}/verification-${width}.png`});
    }
    await dialog.locator('[aria-label="Close application check"]').focus();
    await page.keyboard.press('Shift+Tab');
    assert(await dialog.evaluate(el=>el.contains(document.activeElement)));
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:1440,height:960});
    for(const path of ['/programs/', process.env.QA_PROGRAM_URL, '/results/']) {
      await page.goto(origin+path);
      if(path==='/programs/') {
        await page.locator('.catalog-tabs a').nth(1).click();
        await page.waitForFunction(()=>document.querySelector('.public-browse-status')?.textContent==='Results updated.');
      }
      const url=page.url();
      assert.equal(await page.locator('[data-tracking-open]').getAttribute('aria-haspopup'),'dialog');
      await page.locator('[data-tracking-open]').click();
      await dialog.locator('#id_reference').waitFor();
      assert.equal(page.url(),url);
      await page.keyboard.press('Escape');
    }
    const plain=await browser.newPage({javaScriptEnabled:false});
    await plain.goto(origin+'/resources/');
    await plain.locator('[data-tracking-open]').click();
    assert(new URL(plain.url()).pathname.endsWith('/tracking/'));
    assert(await plain.locator('#id_reference').isVisible());
    await plain.close();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({errors,validation:true,limitedProgress:true,refresh:true,sessionClearing:true,noNavigation:true,noCachedStatusOnClose:true,catalogAfterFiltering:true,programDetail:true,publishedResults:true,keyboard:true,mobile:true,noJavaScriptFallback:true},null,2));
    console.log('Tracking popup validation, private progress, refresh, finish, catalogue/detail/results entry points, mobile and fallback passed.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
