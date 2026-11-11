/* Read-only browser checks against published event cards. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'), fs=require('node:fs');
const origin=process.env.QA_URL || 'http://127.0.0.1:8013';
const output=process.env.QA_OUTPUT || 'docs/public-event-carousel-2026-11-08';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    fs.mkdirSync(output,{recursive:true});
    const page=await browser.newPage(), errors=[], checks=[];
    page.on('pageerror',error=>errors.push(error.message));
    for(const width of [1920,1440,992,768,390,320]) {
      await page.setViewportSize({width,height:960});
      await page.goto(origin+'/events/');
      const deck=page.locator('.event-swipe-carousel'), cards=deck.locator('[data-swipe-card]');
      await page.waitForSelector('.event-swipe-carousel.is-ready');
      assert.equal(await page.locator('#event-period, .portal-section-heading').count(),0);
      const count=await cards.count();
      assert(count>2,'This check needs at least three published events.');
      const visible=cards.locator('visible=true');
      assert.equal(await visible.count(),width>=992?2:1);
      const height=await deck.locator('[data-swipe-viewport]').evaluate(el=>el.clientHeight);
      const seen=new Set();
      for(let index=0;index<count;index++) {
        const items=await visible.evaluateAll(els=>els.map(el=>({label:el.getAttribute('aria-label'),height:el.clientHeight,overflow:el.scrollHeight-el.clientHeight})));
        items.forEach(item=>{seen.add(item.label);assert(item.overflow<=1);assert(Math.abs(item.height-height)<=2);});
        const next=deck.locator('[data-swipe-next]');
        if(await next.getAttribute('aria-disabled')==='true') break;
        const before=await deck.locator('[data-swipe-status]').textContent();
        await next.click();
        await page.waitForFunction(before=>document.querySelector('.event-swipe-carousel [data-swipe-status]').textContent!==before,before);
      }
      assert.equal(seen.size,count);
      // The final lone card stays centered without changing the row height.
      assert(await visible.evaluateAll(els=>{const first=els[0].getBoundingClientRect(), last=els.at(-1).getBoundingClientRect(), p=els[0].parentElement.getBoundingClientRect();return Math.abs(first.left+last.right-p.left-p.right)<=1;}));
      await deck.locator('[data-swipe-viewport]').focus();
      await page.keyboard.press('Home');
      await page.waitForFunction(()=>document.querySelector('.event-swipe-carousel [data-swipe-previous]').getAttribute('aria-disabled')==='true');
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      if([1440,390].includes(width)) await deck.screenshot({path:`${output}/events-${width}.png`});
      checks.push({width,count,visible:await visible.count(),height});
    }
    await page.setViewportSize({width:1440,height:960});
    await page.goto(origin+'/events/');
    const deck=page.locator('.event-swipe-carousel');
    await deck.scrollIntoViewIfNeeded();
    const position=await deck.locator('[data-swipe-card]').first().boundingBox(), start=await deck.locator('[data-swipe-status]').textContent();
    await page.mouse.move(position.x+position.width*.8,position.y+100);
    await page.mouse.down();
    await page.mouse.move(position.x+position.width*.3,position.y+100,{steps:8});
    await page.mouse.up();
    await page.waitForFunction(start=>document.querySelector('.event-swipe-carousel [data-swipe-status]').textContent!==start,start);
    assert.equal(await page.locator('dialog[open]').count(),0,'Swiping a linked card must not open its popup');
    const before=page.url();
    await deck.locator('[data-swipe-card]:not([hidden]) a').click();
    await page.waitForSelector('dialog[open] [data-event-content]');
    assert.equal(page.url(),before);
    await page.keyboard.press('Escape');
    await page.emulateMedia({media:'print'});
    assert.equal(await deck.locator('[data-swipe-card]:visible').count(),await deck.locator('[data-swipe-card]').count());
    const phone=await browser.newPage({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
    await phone.goto(origin+'/events/');
    const phoneDeck=phone.locator('.event-swipe-carousel');
    await phoneDeck.locator('[data-swipe-viewport]').scrollIntoViewIfNeeded();
    const point=await phoneDeck.locator('[data-swipe-card]').first().evaluate(el=>{const r=el.getBoundingClientRect();return {x:r.x+r.width*.8,y:r.y+80};});
    const touch=await phone.context().newCDPSession(phone), first=await phoneDeck.locator('[data-swipe-status]').textContent();
    await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
    for(let i=1;i<=6;i++) await touch.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:point.x-i*20,y:point.y}]});
    await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await phone.waitForFunction(first=>document.querySelector('.event-swipe-carousel [data-swipe-status]').textContent!==first,first);
    assert.equal(await phone.locator('dialog[open]').count(),0);
    await phone.close();
    const plain=await browser.newPage({javaScriptEnabled:false});
    await plain.goto(origin+'/events/');
    assert.equal(await plain.locator('[data-swipe-card]:visible').count(),await plain.locator('[data-swipe-card]').count());
    await plain.close();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,errors,mouseSwipe:true,touchSwipe:true,popup:true,print:true,noJavaScript:true},null,2));
    console.log('Event carousel passed: two desktop cards, one mobile card, every event reachable, stable height, swipe, popup, print and fallback.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
