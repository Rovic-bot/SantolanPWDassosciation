/* Read-only dialog and interaction colour checks against synthetic fixtures. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const {scan} = require('./admin_palette_browser.cjs');
const fixtures=path.resolve('.local/admin-theme-synthetic'), output=path.resolve(process.env.PALETTE_OUTPUT||'.local/admin-palette-final');
const manifest=JSON.parse(fs.readFileSync(path.join(fixtures,'manifest.json'),'utf8'));
const auxiliary=JSON.parse(fs.readFileSync(path.join(fixtures,'dialog-manifest.json'),'utf8'));
const byURL=new Map([...manifest,...auxiliary].map(row=>[row.url,row])), base='http://127.0.0.1:8013';
fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const page=await context.newPage(), errors=[], checks=[];
  page.on('pageerror',error=>errors.push(error.message));
  await context.route('**/*',route=>{
    const req=route.request(),url=new URL(req.url()),row=byURL.get(url.pathname+url.search);
    if(req.method()!=='GET')return route.abort();
    if(url.origin===base&&row)return route.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync(path.join(fixtures,row.file))});
    if(url.origin===base&&url.pathname.startsWith('/static/'))return route.continue();
    return route.fulfill({status:404,body:'Outside the synthetic fixture'});
  });
  const go=name=>page.goto(base+manifest.find(row=>row.name===name).url);
  async function check(label,theme,width){
    const result=await scan(page),overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
    checks.push({label,theme,width,...result,overflow});
    fs.writeFileSync(path.join(output,'dialog-checks.json'),JSON.stringify({checks,errors},null,2));
    assert.deepEqual(result.low,[],label+' '+theme+' text contrast');
    assert(!overflow,label+' overflow');
  }
  try {
    await go('core:dashboard');
    for(const theme of ['light','dark','contrast']){
      await page.evaluate(theme=>{
        localStorage.setItem('santolan-dashboard-theme',theme==='light'?'light':'dark');
        localStorage.setItem('santolan-display',JSON.stringify({contrast:theme==='contrast',motion:true}));
      },theme);
      for(const width of [1440,390]){
        await page.setViewportSize({width,height:1000});
        await go('core:dashboard');
        const triggers=page.locator('[data-open-chart-data]');
        for(let index=0;index<await triggers.count();index++){
          await triggers.nth(index).click();
          const dialog=page.locator('#overview-data-dialog');
          assert(await dialog.evaluate(el=>el.matches(':modal')));
          await check('chart-data-'+index,theme,width);
          if(index===1)await page.screenshot({path:path.join(output,`chart-dialog-${theme}-${width}.png`)});
          await page.keyboard.press('Escape');
          assert(await triggers.nth(index).evaluate(el=>el===document.activeElement));
        }
        await page.getByRole('button',{name:'Display preferences',exact:true}).click();
        await check('display-preferences',theme,width);
        await page.keyboard.press('Escape');

        await go('member_directory');
        const memberURL=manifest.find(row=>row.name==='members:detail').url;
        await page.locator(`a[data-record-dialog][href="${memberURL}"]`).first().click();
        await page.locator('dialog [data-record-content]').waitFor();
        await check('member-record-dialog',theme,width);
        await page.screenshot({path:path.join(output,`member-dialog-${theme}-${width}.png`)});
        await page.keyboard.press('Escape');

        await go('admin:admin_logentry_changelist');
        await page.locator('[data-activity-inspect]').first().click();
        await page.locator('[data-activity-dialog] [data-activity-detail]').waitFor();
        await check('activity-inspect-dialog',theme,width);
        await page.screenshot({path:path.join(output,`activity-dialog-${theme}-${width}.png`)});
        await page.keyboard.press('Escape');

        await go('programs:manage_detail');
        await page.locator('details').evaluateAll(nodes=>nodes.forEach(el=>el.open=true));
        const primary=page.locator('.btn-primary:visible').first();
        if(await primary.count()){
          await primary.hover();
          await check('publication-hover',theme,width);
          await primary.focus();
          await check('publication-focus',theme,width);
        }
        await check('expanded-program-panels',theme,width);
      }
    }
    assert.deepEqual(errors,[]);
    console.log(`PASS: ${checks.length} dialog and interaction states, all three themes, desktop/mobile; no text contrast failures or overflow.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
