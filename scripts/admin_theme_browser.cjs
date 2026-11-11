/* GET-only presentation checks over rendered fixtures; no operational form submissions. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const fixtures = path.resolve(process.env.ADMIN_THEME_FIXTURES || '.local/admin-theme-captures');
const output = path.resolve(process.env.ADMIN_THEME_OUTPUT || '.local/admin-theme-review');
const base = process.env.ADMIN_THEME_BASE_URL || 'http://127.0.0.1:8013';
const interactionsOnly = process.env.ADMIN_THEME_INTERACTIONS_ONLY === '1';
const manifest = JSON.parse(fs.readFileSync(path.join(fixtures,'manifest.json'),'utf8')).filter(row=>row.file);
const selectedNames = process.env.ADMIN_THEME_PAGES?.split(',');
const selectedPages = selectedNames?manifest.filter(row=>selectedNames.includes(row.name)):manifest;
fs.mkdirSync(output,{recursive:true});

(async()=>{
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'dark',reducedMotion:'reduce'});
  const page = await context.newPage(), errors = [], findings = [], checks = [], contrast = [];
  const captureByUrl = new Map(manifest.map(row=>[row.url,row]));
  await context.route('**/*',route=>{
    const request=route.request(), url=new URL(request.url());
    assert.equal(request.method(),'GET','Browser QA never submits operational forms');
    assert.equal(url.origin,base,'No external requests');
    const fixture=captureByUrl.get(url.pathname+url.search);
    if(fixture)return route.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync(path.join(fixtures,fixture.file))});
    if(url.pathname==='/admin/jsi18n/')return route.fulfill({contentType:'application/javascript; charset=utf-8',body:fs.readFileSync(path.join(fixtures,'jsi18n.js'))});
    if(url.pathname.startsWith('/static/'))return route.continue();
    return route.fulfill({status:404,body:'Not part of this read-only fixture'});
  });
  page.on('pageerror',error=>errors.push(error.message));
  try {
    for(const entry of interactionsOnly?[]:selectedPages){
      await page.setViewportSize({width:1440,height:1000});
      await page.goto(base+entry.url,{waitUntil:'load'});
      for(const theme of ['dark','light']){
        // Use the real header control on every full workspace page.
        if(await page.evaluate(()=>document.documentElement.dataset.dashboardTheme)!==theme){
          if(entry.popup)await page.evaluate(theme=>document.documentElement.dataset.dashboardTheme=theme,theme);
          else await page.locator('[data-dashboard-theme-toggle]').click();
        }
        if(!entry.popup){
          const button=page.locator('[data-dashboard-theme-toggle]');
          assert(await button.isVisible(),entry.name+' theme control');
          assert.equal(await button.getAttribute('aria-label'),`Switch to ${theme==='dark'?'light':'dark'} mode`);
          assert.equal(await page.locator('.dashboard-public-link').getAttribute('href'),
            await page.locator('body.onsite-registration-workspace').count() ? '/dashboard/' : '/');
        }
        const palette=await page.evaluate(()=>({color:getComputedStyle(document.body).color,
          surface:getComputedStyle(document.body).getPropertyValue('--surface').trim(),
          font:getComputedStyle(document.body).fontFamily,theme:document.documentElement.dataset.dashboardTheme}));
        assert.equal(palette.color,theme==='dark'?'rgb(244, 242, 236)':'rgb(28, 26, 24)',entry.name+' text palette');
        assert.match(palette.font,/Inter|Segoe UI/,entry.name+' typography');
        const searchOverlap=await page.evaluate(()=>[...document.querySelectorAll('.registration-inbox-search input,.referral-search input,.program-search-control input')].filter(input=>{
          const icon=input.parentElement.querySelector('svg');
          return icon&&input.getBoundingClientRect().left+parseFloat(getComputedStyle(input).paddingLeft)<icon.getBoundingClientRect().right+5;
        }).map(input=>input.id));
        if(searchOverlap.length)findings.push({name:entry.name,theme,searchOverlap});
        const lowContrast=await page.evaluate(()=>{
          const rgb=value=>{
            const channels=(value.match(/[\d.]+/g)||[]).map(Number);
            if(value.startsWith('color(srgb'))for(let i=0;i<3;i++)channels[i]*=255;
            return channels;
          };
          const blend=(fg,bg)=>fg.slice(0,3).map((v,i)=>v*(fg[3]??1)+bg[i]*(1-(fg[3]??1)));
          const luminance=color=>color.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
          return [...document.querySelectorAll('.overview-theme-toggle,.dashboard-public-link,.display-trigger,.btn-primary,input[type=submit],.quiet-badge,.form-control,.form-select,thead th')].filter(el=>el.getClientRects().length&&!el.disabled).flatMap(el=>{
            const ancestors=[];for(let p=el;p;p=p.parentElement)ancestors.unshift(p);
            const bg=ancestors.reduce((bg,p)=>blend(rgb(getComputedStyle(p).backgroundColor),bg),[255,255,255]);
            const fg=blend(rgb(getComputedStyle(el).color),bg), a=luminance(fg), b=luminance(bg);
            const ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
            return ratio<4.5?[{tag:el.tagName,id:el.id,class:el.className,ratio:Number(ratio.toFixed(2))}]:[];
          });
        });
        if(lowContrast.length)contrast.push({name:entry.name,theme,lowContrast});
        for(const width of [1440,1024,768,390,320]){
          await page.setViewportSize({width,height:1000});
          await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
          const overflow=await page.evaluate(()=>{
            if(document.documentElement.scrollWidth<=innerWidth+1)return [];
            return [...document.querySelectorAll('body *')].filter(el=>{
              const r=el.getBoundingClientRect();
              if(!r.width||r.right<=innerWidth+1)return false;
              for(let p=el.parentElement;p&&p!==document.body;p=p.parentElement){
                if(['auto','scroll','hidden','clip'].includes(getComputedStyle(p).overflowX))return false;
              }
              return true;
            }).slice(0,8).map(el=>({tag:el.tagName,id:el.id,class:el.className,right:Math.round(el.getBoundingClientRect().right)}));
          });
          if(overflow.length)findings.push({name:entry.name,theme,width,overflow});
          checks.push({name:entry.name,theme,width});
          if([1440,390].includes(width)&&!entry.popup){
            await page.screenshot({path:path.join(output,`${entry.file.replace('.html','')}-${theme}-${width}.png`)});
          }
        }
      }
      console.log('Checked '+entry.name);
    }
    if(!interactionsOnly)fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({pages:selectedPages.length,checks:checks.length,errors,findings,contrast},null,2));
    // One preference follows navigation between custom and native administration.
    const members=manifest.find(row=>row.name==='member_directory'||row.name==='members:list');
    const user=manifest.find(row=>row.name==='admin:auth_user_change');
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(base+members.url);
    if(await page.evaluate(()=>document.documentElement.dataset.dashboardTheme)!=='dark')await page.locator('[data-dashboard-theme-toggle]').click();
    await page.goto(base+user.url);
    assert.equal(await page.evaluate(()=>document.documentElement.dataset.dashboardTheme),'dark');
    await page.reload();
    assert.equal(await page.evaluate(()=>document.documentElement.dataset.dashboardTheme),'dark');
    await page.locator('[data-dashboard-theme-toggle]').focus();
    assert.equal(await page.locator('[data-dashboard-theme-toggle]').evaluate(el=>getComputedStyle(el).outlineStyle),'solid');
    // Django's dual-list permissions widget still works, without saving the record.
    const available=page.locator('#id_user_permissions_from');
    assert(await available.isVisible(),'Native permissions selector initializes');
    const permission=await available.locator('option').first().getAttribute('value');
    await available.selectOption(permission);
    await page.locator('#id_user_permissions_add').click();
    assert.equal(await page.locator(`#id_user_permissions_to option[value="${permission}"]`).count(),1);
    await page.getByRole('button',{name:'Display preferences',exact:true}).click();
    await page.getByLabel('High contrast',{exact:true}).check();
    assert.equal(await page.evaluate(()=>document.documentElement.dataset.contrast),'true');
    assert.equal(await page.locator('.display-panel').evaluate(el=>getComputedStyle(el).color),'rgb(17, 17, 17)');
    await page.keyboard.press('Escape');
    assert(await page.getByRole('button',{name:'Display preferences',exact:true}).evaluate(el=>el===document.activeElement));
    // Display preferences continue across admin tabs, including enlarged text/mobile navigation.
    await page.goto(base+members.url);
    assert.equal(await page.evaluate(()=>document.documentElement.dataset.contrast),'true');
    await page.setViewportSize({width:320,height:1000});
    await page.getByRole('button',{name:'Display preferences',exact:true}).click();
    await page.getByLabel('Text size',{exact:true}).selectOption('largest');
    await page.getByLabel('Reduce motion',{exact:true}).check();
    await page.keyboard.press('Escape');
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),'Large text mobile overflow');
    await page.getByRole('button',{name:/Workspace menu/}).click();
    await page.locator('#admin-nav.show').waitFor();
    assert(await page.locator('#admin-nav').isVisible());
    await page.keyboard.press('Escape');
    await page.locator('#admin-nav').waitFor({state:'hidden'});
    assert(!await page.locator('#admin-nav').isVisible());
    fs.writeFileSync(path.join(output,interactionsOnly?'interactions.json':'results.json'),JSON.stringify({pages:selectedPages.length,checks:checks.length,errors,findings,contrast,interactions:'passed'},null,2));
    assert.deepEqual(errors,[],'JavaScript errors');
    assert.deepEqual(findings,[],'Responsive overflow; see results.json');
    assert.deepEqual(contrast,[],'Text/controls contrast; see results.json');
    console.log(interactionsOnly?'PASS: theme persistence, focus, native permissions picker, Display preferences, enlarged text and mobile navigation.':`PASS: ${selectedPages.length} admin pages, both themes, ${checks.length} responsive checks; control/text contrast and interactions passed.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
