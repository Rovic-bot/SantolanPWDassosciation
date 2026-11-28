"use strict";
const fs = require('node:fs'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
 const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const results = [];
 try {
  for (const width of [1366,390]) for (const route of ['/dashboard/','/ewaf/','/membership/registration/pdao/onsite/']) {
   const context = await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
   await context.addCookies([{name:'sessionid',value:process.env.QA_SESSION,url:process.env.QA_URL}]);
   await context.route('**/*', r=>new URL(r.request().url()).origin === process.env.QA_URL ? r.continue() : r.abort());
   await context.addInitScript(()=>{
    window.shifts=[];
    new PerformanceObserver(list=>{for (const e of list.getEntries()) if(!e.hadRecentInput) window.shifts.push({t:e.startTime,value:e.value,sources:e.sources.map(s=>({node:s.node?.tagName+'.'+s.node?.className,old:s.previousRect.toJSON(),next:s.currentRect.toJSON()}))});}).observe({type:'layout-shift',buffered:true});
   });
   const page = await context.newPage();
   const response=await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'});
   await page.waitForTimeout(800);
   const shifts=await page.evaluate(()=>window.shifts);
   results.push({route,width,status:response.status(),cls:shifts.reduce((s,x)=>s+x.value,0),shifts});
   await context.close();
  }
 } finally {await browser.close();fs.writeFileSync(process.env.QA_OUTPUT,JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results.map(({route,width,cls})=>({route,width,cls}))));
 if(results.some(r=>r.status!==200||r.cls>0.1)) throw new Error('Layout shift acceptance failed; inspect local trace.');
})().catch(e=>{console.error(e);process.exit(1)});
