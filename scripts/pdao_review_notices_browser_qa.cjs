const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
function scanContrast(){
 const rgba=s=>(s.match(/[\d.]+/g)||[]).map(Number);
 const lum=v=>v.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:Math.pow((x+.055)/1.055,2.4)}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
 const bad=[];let count=0,min=100;
 const w=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);
 while(w.nextNode()){
  const t=w.currentNode,e=t.parentElement;
  if(!t.textContent.trim()||e.closest('[hidden],[inert],[aria-hidden="true"],.visually-hidden,script,style,option'))continue;
  const cs=getComputedStyle(e);if(cs.visibility==='hidden'||!e.getClientRects().length)continue;
  let bg;
  for(let n=e;n;n=n.parentElement){const c=rgba(getComputedStyle(n).backgroundColor);if(c.length===3||c[3]>.98){bg=c;break;}}
  bg??=[255,255,255];const fg=rgba(cs.color);if(fg.length<3)continue;
  const a=lum(fg),b=lum(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
  count++;min=Math.min(min,ratio);
  if(ratio<4.45)bad.push({text:t.textContent.trim().slice(0,70),class:e.className,ratio,fg:cs.color,bg});
 }
 return {count,min,bad};
}
(async () => {
  const browser = await chromium.launch({headless:true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const errors = [], url=process.env.QA_URL, output=process.env.QA_OUTPUT;
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.addCookies([{name:'sessionid',value:process.env.QA_ADMIN_SESSION,url}]);
    await context.route('https://registry.example.test/**', route=>route.fulfill({body:'<h1>Synthetic manual registry</h1>',contentType:'text/html'}));
    const page=await context.newPage(); page.on('pageerror', error=>errors.push(error.message));
    let readyPosts = 0;
    page.on('request', request => {
      if (request.method() === 'POST' && new URLSearchParams(request.postData()).get('action') === 'ready') readyPosts++;
    });
    const confirmReady = async channel => {
      const button = page.getByRole('button', {name:'Mark ready to forward', exact:true});
      const dialog = page.locator('#pdao-ready-dialog');
      const oldStatus = await page.locator('.pdao-status').innerText(), before = readyPosts;
      await button.click();
      await dialog.waitFor({state:'visible'});
      assert.equal(await dialog.locator('[autofocus]').evaluate(el => el === document.activeElement), true);
      assert.equal(readyPosts, before);
      if (channel === 'online') assert((await dialog.innerText()).includes('office-verification invitation'));
      else assert((await dialog.innerText()).includes('No review email will be sent'));
      for (const width of [1440,390,320]) {
        await page.setViewportSize({width,height:1000});
        assert(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
        await dialog.screenshot({path:path.join(output,`ready-${channel}-${width}.png`)});
      }
      await dialog.getByRole('button', {name:'Cancel', exact:true}).click();
      await dialog.waitFor({state:'hidden'});
      assert.equal(readyPosts, before);
      assert.equal(await page.locator('.pdao-status').innerText(), oldStatus);
      assert.equal(await button.evaluate(el => el === document.activeElement), true);
      await button.click();
      await page.keyboard.press('Escape');
      await dialog.waitFor({state:'hidden'});
      assert.equal(readyPosts, before);
      await button.focus();
      await page.keyboard.press('Enter');
      await dialog.waitFor({state:'visible'});
      // Two rapid confirmation clicks still make only one state-changing request.
      await dialog.locator('[data-pdao-ready-confirm]').evaluate(el => {el.click(); el.click();});
      await page.locator('#pdao-forward-form input[name=confirmed]').waitFor();
      assert.equal(readyPosts, before + 1);
      await page.setViewportSize({width:1440,height:1000});
    };
    const openRegistry=async()=>{
      const opened=context.waitForEvent('page');
      await page.locator('[data-pdao-registry-open]').click();
      const tab=await opened; await tab.waitForURL('https://registry.example.test/check'); await tab.close();
    };
    await page.goto(url+process.env.QA_ONLINE);
    const nojs = await browser.newContext({javaScriptEnabled:false});
    await nojs.addCookies([{name:'sessionid',value:process.env.QA_ADMIN_SESSION,url}]);
    const plain = await nojs.newPage();
    await plain.goto(url+process.env.QA_ONLINE);
    assert(await plain.locator('[name=ready_confirmed]').isVisible());
    assert.equal(await plain.locator('#pdao-ready-dialog').isVisible(), false);
    await nojs.close();
    assert(await page.locator('[data-pdao-decision]').first().isDisabled());
    await openRegistry();
    assert(await page.locator('[data-pdao-decision]').first().isEnabled());
    await page.locator('.pdao-information-request summary').click();
    await page.locator('#needs_reason').fill('Please check the PWD number and correct the spelling of your name.');
    for (const width of [1440,390,320]) {
      await page.setViewportSize({width,height:1000});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await page.locator('#pdao-processing').screenshot({path:path.join(output,`review-${width}.png`)});
    }
    await page.getByRole('button',{name:'Send email and mark needs information',exact:true}).click();
    await page.getByText('Needs information',{exact:true}).first().waitFor();
    assert.equal(await page.locator('.pdao-status').innerText(),'Needs information');
    await page.locator('.pdao-email-status').waitFor();
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('#id_first_name').fill('Reviewed');
    await page.getByRole('button',{name:'Save reviewed details',exact:true}).click();
    await page.getByRole('heading',{name:'Reviewed Example',exact:true}).waitFor();
    assert(await page.getByRole('button',{name:'Mark ready to forward',exact:true}).isDisabled());
    await openRegistry();
    await confirmReady('online');
    assert.equal(await page.locator('.pdao-status').innerText(),'Ready to forward');
    await page.locator('.pdao-email-status').screenshot({path:path.join(output,'email-status.png')});
    await page.locator('#pdao-forward-form input[name=confirmed]').check();
    await page.getByRole('button',{name:'Record forwarded to PDAO',exact:true}).click();
    await page.getByText('These details are now locked.',{exact:false}).waitFor();
    await page.goto(url+process.env.QA_ONSITE);
    assert.equal(await page.locator('[data-pdao-registry-open],.pdao-information-request,.pdao-email-status').count(),0);
    await confirmReady('onsite');
    await page.locator('#pdao-forward-form input[name=confirmed]').check();
    await page.getByRole('button',{name:'Record forwarded to PDAO',exact:true}).click();
    await page.getByText('These details are now locked.',{exact:false}).waitFor();

    const pub=await browser.newContext({viewport:{width:1440,height:1000}});
    await pub.addCookies([{name:'sessionid',value:process.env.QA_PUBLIC_SESSION,url}]);
    const receipt=await pub.newPage(); receipt.on('pageerror',error=>errors.push(error.message));
    await receipt.goto(url+'/membership/registration/pdao/receipt/');
    await receipt.locator('.pdao-receipt-shell').waitFor();
    for (const mode of ['light','dark','contrast']) {
      await receipt.evaluate(mode=>{
        document.documentElement.dataset.publicTheme=mode==='dark'?'dark':'light';
        document.documentElement.dataset.contrast=String(mode==='contrast');
      },mode);
      await receipt.evaluate(async () => {
        await Promise.all(document.getAnimations().filter(animation =>
          Number.isFinite(animation.effect.getComputedTiming().endTime)).map(animation => animation.finished.catch(() => {})));
      });
      for(const width of [1440,768,390,320]) {
        await receipt.setViewportSize({width,height:1000});
        assert(await receipt.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${mode} ${width}`);
        const contrast=await receipt.evaluate(scanContrast);
        assert.deepEqual(contrast.bad,[], `${mode} ${width} text contrast`);
        if([1440,390].includes(width)) await receipt.screenshot({path:path.join(output,`receipt-${mode}-${width}.png`),fullPage:true});
      }
    }
    await receipt.locator('.pdao-copy-preview summary').click();
    const frame=receipt.frameLocator('[data-pdao-receipt-frame]');
    await frame.locator('.pdao-sheet').first().waitFor();
    assert(await frame.locator('body').textContent().then(text=>text.includes('Fictional Example')));
    await frame.locator('body').evaluate(()=>{window.print=()=>{window.receiptPrinted=true;};});
    await receipt.locator('[data-pdao-receipt-print]').click();
    assert(await frame.locator('body').evaluate(()=>window.receiptPrinted));
    const source=await pub.newPage(); await source.goto(url+'/membership/registration/pdao/receipt/form/?preview=1');
    const pdf=await source.pdf({path:path.join(output,'submitted-form.pdf'),preferCSSPageSize:true,printBackground:true});
    assert.equal((pdf.toString('latin1').match(/\/Type \/Page\b/g)||[]).length,2);
    await source.close();
    await receipt.getByRole('button',{name:'Finish and close private receipt',exact:true}).click();
    await receipt.waitForURL('**/membership/register/');
    assert.equal((await pub.request.get(url+'/membership/registration/pdao/receipt/form/')).status(),404);
    assert.deepEqual(errors,[]);
    console.log('Ready confirmation: Cancel/Escape/keyboard/focus/mobile/double-click passed for online and onsite. Online manual review, two captured notices, onsite no-email forwarding, private receipt themes/mobile/printing and revocation passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
