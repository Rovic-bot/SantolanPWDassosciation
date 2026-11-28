'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const engines = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const engine = process.env.QA_ENGINE, base = process.env.QA_URL, output = process.env.QA_OUTPUT;
const axe = process.env.QA_AXE_PATH || require.resolve('axe-core/axe.min.js');
(async () => {
  assert(['firefox','webkit'].includes(engine));
  const browser = await engines[engine].launch({headless:true});
  const results = [], errors = [], preferences = [];
  try {
    const context = await browser.newContext({reducedMotion:'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => {
      if (response.url().startsWith(base) && response.status() >= 400) errors.push(`${new URL(response.url()).pathname}: HTTP ${response.status()}`);
    });
    for (const [kind,routes] of [['public',JSON.parse(process.env.QA_ROUTES)],['staff',JSON.parse(process.env.QA_STAFF)]]) {
      if (kind === 'staff') await context.addCookies([{name:'sessionid',value:process.env.QA_SESSION,url:base}]);
      for (const route of routes) {
        await page.setViewportSize({width:1366,height:900});
        const response = await page.goto(base + route,{waitUntil:'networkidle'});
        await page.addScriptTag({path:axe});
        const violations = await page.evaluate(async () => (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)})));
        const widths = [];
        for (const width of [320,375,390,430,768,1024,1366,1440]) {
          await page.setViewportSize({width,height:900});
          await page.waitForTimeout(60);
          widths.push({width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)});
        }
        if (route === '/' || route === '/dashboard/') {
          const trigger = page.locator('.display-trigger');
          await trigger.focus(); await page.keyboard.press('Enter');
          const opens = await page.locator('#display-size').evaluate(el=>document.activeElement===el);
          await page.locator('#display-size').selectOption('largest');
          await page.keyboard.press('Escape');
          const returns = await trigger.evaluate(el=>document.activeElement===el);
          await page.setViewportSize({width:320,height:900});
          const largeTextOverflow = await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
          await trigger.click(); await page.locator('.display-reset').click(); await page.keyboard.press('Escape');
          preferences.push({route,opens,returns,largeTextOverflow});
        }
        await page.setViewportSize({width:320,height:900});
        await page.screenshot({path:path.join(output,`${kind}-${results.length}-320.png`),fullPage:true});
        results.push({route,status:response.status(),violations,widths});
        fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({engine,results,errors,preferences},null,2));
      }
    }
    assert(results.every(r=>r.status===200),'All routes must finish with HTTP 200');
    assert(results.every(r=>r.violations.length===0),'Accessibility violations remain');
    assert(results.every(r=>r.widths.every(w=>!w.overflow)),'Horizontal overflow remains');
    assert(preferences.every(p=>p.opens && p.returns && !p.largeTextOverflow),'Keyboard or enlarged-text failure');
    assert.equal(errors.length,0,'Browser errors remain');
    console.log(JSON.stringify({engine,routes:results.length,widthChecks:results.reduce((n,r)=>n+r.widths.length,0),errors:errors.length,violations:results.reduce((n,r)=>n+r.violations.length,0)}));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
