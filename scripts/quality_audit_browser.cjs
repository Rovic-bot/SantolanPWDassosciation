'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const base = process.env.QA_URL, output = process.env.QA_OUTPUT;
const axe = process.env.QA_AXE_PATH || require.resolve('axe-core/axe.min.js');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const results = [], errors = [], blocked = new Set(), mobileLab = [], preferenceChecks = [];
  try {
    const context = await browser.newContext({reducedMotion:'reduce'});
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin === base) return route.continue();
      blocked.add(route.request().url()); return route.abort();
    });
    await context.addInitScript(() => {
      window.auditVitals = {lcp: null, cls: 0, shifts: []};
      new PerformanceObserver(list => {for (const e of list.getEntries()) window.auditVitals.lcp = e.startTime;}).observe({type:'largest-contentful-paint',buffered:true});
      new PerformanceObserver(list => {for (const e of list.getEntries()) if (!e.hadRecentInput) {window.auditVitals.cls += e.value;window.auditVitals.shifts.push({time:e.startTime,value:e.value,sources:e.sources.map(s=>s.node?.tagName+'.'+s.node?.className)});}}).observe({type:'layout-shift',buffered:true});
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push({url:page.url().replace(base,''),message:error.message}));
    page.on('response', response => {
      const url = new URL(response.url());
      if (url.origin === base && response.status() >= 400) {
        errors.push({url:url.pathname,status:response.status(),message:'Failed HTTP response'});
      }
    });
    page.on('requestfailed', request => {
      const url = new URL(request.url()), message = request.failure()?.errorText;
      // Navigating away can cancel polling; unrelated outbound requests are blocked intentionally.
      if (url.origin === base && message !== 'net::ERR_ABORTED') errors.push({url:url.pathname,message});
    });
    for (const [kind, routes] of [['public',JSON.parse(process.env.QA_ROUTES)],['staff',JSON.parse(process.env.QA_STAFF)]]) {
      if (kind === 'staff') await context.addCookies([{name:'sessionid',value:process.env.QA_SESSION,url:base}]);
      for (const route of routes) {
        await page.setViewportSize({width:1366,height:900});
        const response = await page.goto(base + route, {waitUntil:'networkidle'});
        const metrics = await page.evaluate(() => {
          const n = performance.getEntriesByType('navigation')[0];
          const resources = performance.getEntriesByType('resource');
          return {...window.auditVitals, ttfb:n.responseStart, load:n.loadEventEnd, requests:resources.length+1,
            bytes:resources.reduce((sum,r)=>sum+r.transferSize, n.transferSize)};
        });
        await page.addScriptTag({path:axe});
        const accessibility = await page.evaluate(async () => {
          const r = await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});
          return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}));
        });
        const widths = [];
        for (const width of [320,375,390,430,768,1024,1366,1440]) {
          await page.setViewportSize({width,height:900});
          await page.waitForTimeout(60);
          widths.push({width,...await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,
            scrollWidth:document.documentElement.scrollWidth}))});
        }
        await page.setViewportSize({width:320,height:900});
        await page.screenshot({path:path.join(output,`${kind}-${results.length}-320.png`),fullPage:true});
        await page.keyboard.press('Tab');
        const focus = await page.locator(':focus').evaluate(el=>({tag:el.tagName,text:el.textContent.trim().slice(0,60)})).catch(()=>null);
        results.push({kind,route,status:response.status(),finalPath:new URL(page.url()).pathname,metrics,accessibility,widths,firstFocus:focus});
        if (['/', '/dashboard/'].includes(route)) {
          const trigger = page.locator('.display-trigger');
          await trigger.focus(); await page.keyboard.press('Enter');
          const keyboardOpens = await page.locator('#display-size').evaluate(el=>document.activeElement===el);
          await page.locator('#display-size').selectOption('largest');
          await page.keyboard.press('Escape');
          const keyboardReturns = await trigger.evaluate(el=>document.activeElement===el);
          const largeTextOverflow = await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
          const themes = [];
          for (const mode of ['dark','contrast']) {
            await trigger.click(); await page.locator(`[data-preference="${mode}"]`).check();
            await page.keyboard.press('Escape');
            const violations = await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})));
            themes.push({mode,violations});
          }
          await trigger.click(); await page.locator('.display-reset').click(); await page.keyboard.press('Escape');
          preferenceChecks.push({route,keyboardOpens,keyboardReturns,largeTextOverflow,themes});
        }
        fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,errors,blocked:[...blocked]},null,2));
      }
    }
    await context.clearCookies();
    await page.setViewportSize({width:390,height:844});
    const cdp = await context.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
    await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:500000,uploadThroughput:125000});
    await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
    for (let run=1;run<=3;run++) {
      await page.goto(base+'/',{waitUntil:'networkidle'});
      await page.waitForTimeout(1000);
      mobileLab.push({run,...await page.evaluate(()=>({...window.auditVitals,load:performance.getEntriesByType('navigation')[0].loadEventEnd}))});
    }
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,errors,blocked:[...blocked],mobileLab,preferenceChecks},null,2));
    console.log(JSON.stringify({pages:results.length,overflow:results.flatMap(r=>r.widths.filter(w=>w.overflow).map(w=>({route:r.route,width:w.width}))),violations:results.reduce((n,r)=>n+r.accessibility.length,0),errors}));
    assert(results.every(result => result.status === 200), 'Every audited route must finish with HTTP 200');
    assert(results.every(result => result.accessibility.length === 0), 'Resolve the recorded automated accessibility violations');
    assert(results.every(result => result.widths.every(width => !width.overflow)), 'Resolve the recorded viewport overflow');
    assert(preferenceChecks.every(check => check.keyboardOpens && check.keyboardReturns && !check.largeTextOverflow &&
      check.themes.every(theme => theme.violations.length === 0)), 'Display preferences must remain keyboard accessible in every audited theme');
    assert.deepEqual(errors, [], 'Audited pages must have no JavaScript, HTTP or network failures');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
