const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
 '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const base=process.env.QA_URL,output=process.env.QA_OUTPUT,errors=[],writes=[],checks=[];
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.route(base+'/**',route=>{
   if(route.request().method()!=='GET'){writes.push(route.request().method());return route.abort();}
   return route.continue();
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/programs/');
  const routes=[{name:'catalog',url:'/programs/?q=SYNTHETIC+Closing+program',selector:'.catalog-card'},
                {name:'detail',url:process.env.QA_DETAIL,selector:'.program-detail-overview'}];
  for(const mode of [{name:'light',dark:false,contrast:false},{name:'dark',dark:true,contrast:false},{name:'high-contrast',dark:true,contrast:true}])for(const width of [1440,390])for(const route of routes){
   await page.setViewportSize({width,height:1000});
   await page.evaluate(mode=>localStorage.setItem('santolan-display',JSON.stringify({...mode,motion:true})),mode);
   await page.goto(base+route.url);
   const note=page.locator('[data-public-deadline]');assert(await note.isVisible());
   assert((await note.textContent()).includes('Closing soon.'));assert((await note.textContent()).includes('(PHT)'));
   const state=await note.evaluate(el=>{
    const s=getComputedStyle(el),lum=c=>c.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
    const bg=lum(s.backgroundColor),ratios=[el,...el.querySelectorAll('span,strong,time')].map(n=>{const fg=lum(getComputedStyle(n).color);return(Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05);});
    return {minContrast:Math.min(...ratios),overflow:document.documentElement.scrollWidth>innerWidth+1,clipped:el.scrollHeight>el.clientHeight+1};
   });
   assert(state.minContrast>=4.5);assert.equal(state.overflow,false);assert.equal(state.clipped,false);
   await page.locator(route.selector).screenshot({path:path.join(output,`${route.name}-${mode.name}-${width}.png`),style:'.accessibility-widget,.portal-navigation,.skip-link{visibility:hidden!important}'});
   checks.push({mode:mode.name,width,page:route.name,...state});
  }
  await page.goto(base+'/programs/?q=SYNTHETIC+Closing+program');
  await page.locator('.catalog-tab').filter({hasText:/^Open/}).click();await page.waitForURL('**/programs/?period=available**');
  assert(await page.locator('[data-public-deadline]').isVisible());
  // Use an intentionally wrong device date: timing remains anchored to the server.
  const timed=await context.newPage();timed.on('pageerror',e=>errors.push(e.message));
  await timed.clock.install({time:new Date('2000-01-01T00:00:00Z')});
  await timed.clock.pauseAt(new Date('2000-01-01T00:00:01Z'));
  for(const route of [process.env.QA_LATER,'/programs/?q=SYNTHETIC+Later+registration']){
   await timed.goto(base+route);
   const note=timed.locator('[data-public-deadline]');assert(await note.isHidden());
   const untilStart=await note.evaluate(el=>Date.parse(el.dataset.noticeStart)-Date.parse(el.dataset.noticeNow));
   assert(untilStart>0);
   await timed.clock.runFor(untilStart-1);assert(await note.isHidden());
   await timed.clock.runFor(1);assert(await note.isVisible());
   await timed.clock.fastForward(3600000);assert(await note.isHidden());
  }
  const nojs=await browser.newContext({javaScriptEnabled:false});const plain=await nojs.newPage();
  await plain.goto(base+process.env.QA_DETAIL);assert(await plain.locator('[data-public-deadline]').isVisible());
  await plain.goto(base+process.env.QA_LATER);assert(await plain.locator('[data-public-deadline]').isHidden());
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({checks,liveBoundary:true,serverClock:true,ajax:true,noJavaScript:true,errors,writes},null,2));
  console.log('Closing-soon notices passed: both pages, live one-hour start/expiry, server-relative time, AJAX, no JavaScript and responsive theme contrast.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
