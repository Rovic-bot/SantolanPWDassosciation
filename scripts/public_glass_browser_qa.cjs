/* Run against the retained local development system. All requests in this pass are read-only. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const modules = path.join(process.env.USERPROFILE || '', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(modules,'playwright'));
const {PNG} = require(require.resolve('pngjs',{paths:[modules,__dirname]}));
const base = process.env.PUBLIC_GLASS_BASE || 'http://127.0.0.1:8013';
const output = path.resolve(process.env.PUBLIC_GLASS_OUTPUT || '.local/public-glass-qa');
const sections = [['home','/'],['about','/about/'],['announcements','/announcements/'],['events','/events/'],['programs','/programs/'],['results','/results/'],['membership','/membership/register/'],['resources','/resources/']];
fs.mkdirSync(output,{recursive:true});
const issues=[], stats={routes:0,images:0,textSamples:0,minimumNormal:100,minimumLarge:100}, detailLinks=new Set();
const [mode='capture',size='1440']=process.argv.slice(2), width=Number(size);
const height=width>=1000?960:width===768?1024:844;
const rgb=s=>s.match(/[\d.]+/g).map(Number);
function lum(a){return a.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0)}
function ratio(a,b){let x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
async function contrast(page,label) {
  // Hide glyph paint only. Gradients, blur, backing images and focus/selection surfaces still render.
  const samples=await page.evaluate(()=>{
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),rows=[];
    for(let node;node=walker.nextNode();){
      const el=node.parentElement;if(!node.textContent.trim()||!el||el.closest('svg,script,style,noscript,[hidden],[aria-hidden=true],.visually-hidden,option,textarea,button:disabled'))continue;
      const range=document.createRange();range.selectNodeContents(node);
      const style=getComputedStyle(el);if(style.visibility!=='visible')continue;
      const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.666&&Number(style.fontWeight)>=700);
      const rect=[...range.getClientRects()].find(r=>r.width>3&&r.height>3&&r.top>=0&&r.bottom<innerHeight&&r.left>=0&&r.right<innerWidth);
      if(!rect)continue;
      for (const f of [.23,.64]){
        const x=Math.floor(rect.left+rect.width*f),y=Math.floor((rect.top+rect.bottom)/2);
        if(!el.contains(document.elementFromPoint(x,y)))continue;
        rows.push({x,y,fg:style.color,large,key:el.tagName+'.'+el.className,text:node.textContent.trim().slice(0,40)});
      }
    }return rows;
  });
  const hide=await page.addStyleTag({content:'* { -webkit-text-fill-color:transparent !important;text-shadow:none !important; }'});
  const bitmap=PNG.sync.read(await page.screenshot({animations:'disabled'})); await hide.evaluate(n=>n.remove());
  const seen=new Set();
  for(const {x,y,fg,large,key,text} of samples){
    const i=(y*bitmap.width+x)*4,bg=[...bitmap.data.subarray(i,i+3)],c=rgb(fg);
    const val=ratio(c.slice(0,3).map((n,i)=>n*(c[3]??1)+bg[i]*(1-(c[3]??1))),bg);stats.textSamples++;
    const bucket=large?'minimumLarge':'minimumNormal'; stats[bucket]=Math.min(stats[bucket],val);
    if(val<(large?3:4.5)-.008&&!seen.has(key+text)){seen.add(key+text);issues.push([label,'text contrast',key,text,val.toFixed(2),fg,bg.join(',')]);}
  }
}
async function fit(page,label){
  const state=await page.evaluate(()=>({width:innerWidth,doc:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('main *,header *,footer *,[data-display-widget] *')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().right>innerWidth+1&&!e.closest('svg,.table-responsive,.visually-hidden')).map(e=>e.tagName+'.'+e.className).slice(0,6)}));
  if(state.doc>state.width+1)issues.push([label,'reflow',state]); return state;
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||undefined,args:['--disable-gpu','--disable-features=BackForwardCache']});
 try{
  const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1,colorScheme:'light',reducedMotion:'reduce'});page.setDefaultTimeout(5000);
  page.on('pageerror',e=>issues.push(['js',e.message]));
  await page.route('**/*',route=>{const r=route.request();if(r.method()!=='GET'&&r.method()!=='HEAD')return route.abort();return route.continue();});
  async function visit(url){const response=await page.goto(new URL(url,base).href,{waitUntil:'load'});return response.status();}
  if (mode==='capture'||mode==='enlarged') {
   if(mode==='enlarged') await page.addInitScript(()=>{localStorage.setItem('santolan-display',JSON.stringify({text:'largest',contrast:true,motion:true}));});
   for(const [name,route] of sections){
    assert.equal(await visit(route),200,route);stats.routes++;
    if(mode==='enlarged')await page.addStyleTag({content:'html[data-text] { font-size:200% !important; }'});
    assert.equal(await page.locator('h1').count(),1,route);
    const nav=page.locator('#public-nav .navbar-nav');assert.deepEqual(await nav.locator('a').evaluateAll(a=>a.map(n=>new URL(n.href).pathname)),sections.map(r=>r[1]),route);
    assert.equal(await nav.locator('[aria-current=page]').getAttribute('href'),route);
    assert.ok(await page.locator('link[href*="public-glass.css"]').count());await fit(page,name);
    for(const link of await page.locator('main a[href]').evaluateAll(a=>a.map(n=>n.getAttribute('href')).filter(x=>x.startsWith('/')&&!x.includes('#'))))detailLinks.add(link);
    if(mode==='capture'){
      const imgs=await page.locator('main img,.portal-brand img').evaluateAll(async imgs=>{for(const el of imgs){if(!el.complete&&el.loading==='lazy')el.loading='eager';}return await Promise.all(imgs.map(async n=>{try{await n.decode();}catch{}return {ok:n.naturalWidth>0,src:n.currentSrc};}));});
      stats.images+=imgs.length;imgs.filter(i=>!i.ok).forEach(i=>issues.push([name,'image',i.src]));
      if(width===1440||width===390){
       await page.screenshot({path:path.join(output,name+'-'+width+'.jpg'),type:'jpeg',quality:80,fullPage:true,animations:'disabled'});
       if(width===1440||width===390){await contrast(page,name+' top');await page.evaluate(()=>scrollTo(0,Math.min(innerHeight*.78,document.documentElement.scrollHeight-innerHeight)));await contrast(page,name+' body');}
      }
    }else{
      assert.equal(await page.locator('html').getAttribute('data-contrast'),'true');
      const toggle=page.locator('[aria-controls=public-nav]');
      if(await toggle.isVisible()){await toggle.focus();await page.keyboard.press('Enter');await nav.waitFor({state:'visible'});await fit(page,name+' menu');await page.keyboard.press('Escape');await nav.waitFor({state:'hidden'});assert.ok(await toggle.evaluate(e=>e===document.activeElement));}
    }
    console.log(mode,width,name,'ok');
   }
   fs.writeFileSync(path.join(output,'links-'+width+'.json'),JSON.stringify([...detailLinks],null,2));
  }else if(mode==='flows'){
    await visit('/');await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.className),'skip-link');
    await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>document.activeElement.id),'main-content');
    await page.setViewportSize({width:390,height:844});await page.locator('[aria-controls=public-nav]').click();
    await page.locator('#public-nav.show').waitFor();const navLinks=page.locator('#public-nav .navbar-nav a');
    assert.equal(await navLinks.count(),8);await navLinks.nth(7).focus();await page.keyboard.press('Escape');
    await page.locator('#public-nav').waitFor({state:'hidden'});assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('aria-controls')),'public-nav');
    await page.locator('[aria-controls=public-nav]').click();await page.locator('.menu-tools [data-open-display]').click();
    await page.locator('.display-panel').waitFor();await page.locator('[data-preference=contrast]').check();
    await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('aria-controls')),'public-nav');
    await page.locator('.display-trigger').click();await page.locator('.display-reset').click();await page.keyboard.press('Escape');
    await page.setViewportSize({width,height});
    await visit('/announcements/');await page.locator('#announcement-search').fill('no-match-qa-santolan-5937');
    await page.locator('.notice-search button').click();await page.locator('.notice-empty').waitFor();await page.getByRole('link',{name:'Clear filters'}).click();
    const topic=page.locator('.notice-topic-links a[href*="programs"]').first();await topic.click();assert.ok(await page.locator('#notice-disability').isVisible());
    await visit('/programs/');await page.locator('#program-search').fill('no-match-qa-santolan-5937');await page.locator('.catalog-filter-button').click();
    assert.ok(await page.locator('.catalog-empty').isVisible());await page.locator('.catalog-active-filters a').click();
    assert.equal(await page.locator('#program-search').inputValue(),'');const period=page.locator('.catalog-schedule').first();
    if(await period.count()){await period.locator('summary').click();assert.ok(await period.evaluate(el=>el.open));}
    const next=page.locator('.catalog-pagination [rel=next]');if(await next.count()){await next.click();assert.equal(await page.locator('.catalog-pagination [aria-current]').innerText(),'2');}
    await visit('/events/');await page.locator('#event-period').selectOption('past');await page.locator('.portal-filter-bar button').click();
    assert.equal(await page.locator('#event-period').inputValue(),'past');
    if(await page.locator('[data-view=months]').isVisible()){await page.locator('[data-view=months]').click();assert.equal(await page.locator('[data-observance-view]').getAttribute('data-observance-view'),'months');await page.locator('[data-view=list]').click();}
    await visit('/membership/register/#pdao-requirements-heading');await page.locator('#pdao-service').waitFor();
    await page.locator('#pdao-tab').focus();await page.keyboard.press('ArrowLeft');const check=page.locator('#association-requirements input').first();await check.check();
    await page.locator('#association-tab').focus();await page.keyboard.press('End');await page.keyboard.press('Home');assert.ok(await check.isChecked());
    for(const name of ['association','pdao']){const pdf=await page.request.get(base+'/membership/registration/forms/'+name+'/');assert.ok(pdf.ok());assert.equal((await pdf.body()).subarray(0,5).toString(),'%PDF-');}
    await visit('/membership/registration/apply/');const opener=page.locator('[data-registration-privacy-open]');
    await opener.focus();await page.keyboard.press('Enter');assert.ok(await page.locator('dialog[open]').isVisible());await page.keyboard.press('Escape');
    assert.ok(await opener.evaluate(n=>n===document.activeElement));
    const directory=page.locator('[data-form-directory]');if(!await directory.evaluate(n=>n.open))await directory.locator('summary').click();
    const section=directory.locator('a').nth(1);const target=await section.getAttribute('href');await section.click();assert.equal(await page.evaluate(()=>document.activeElement.id),target.slice(1));
    const required=page.locator('form input[required]:visible').first();assert.ok(await required.count());assert.ok(await required.evaluate(n=>Array.from(n.labels||[]).some(l=>l.innerText.trim())&&!n.form.checkValidity()));
    await visit('/resources/#faq');await page.getByText('Can someone help me use this website?',{exact:true}).click();await page.locator('#faq [data-open-display]').click();
    await page.locator('[data-preference=text]').selectOption('largest');await page.locator('[data-preference=contrast]').check();await page.keyboard.press('Escape');
    await visit('/');assert.equal(await page.locator('html').getAttribute('data-contrast'),'true');
    assert.ok(await page.locator('.welcome-glass').evaluate(n=>getComputedStyle(n).backgroundImage==='none'&&getComputedStyle(n).backdropFilter==='none'));
    await page.emulateMedia({forcedColors:'active',reducedMotion:'reduce'});await page.locator('.welcome-actions a').first().focus();
    assert.ok(await page.locator('.welcome-actions a').first().evaluate(n=>getComputedStyle(n).outlineStyle!=='none'));
    console.log('Keyboard menu, focus return, display settings, search, filters, paging, events, membership tabs, checklists, both PDFs, privacy dialog, form validation, and forced colors passed.');
  }else if(mode==='boundaries'){
    const controls=[
      ['/','.welcome-actions .btn-primary'],['/','.welcome-actions .btn-outline-primary'],
      ['/announcements/','#announcement-search'],['/announcements/','.notice-topic-links [aria-current]'],
      ['/programs/','#program-search'],['/programs/','#program-category'],['/programs/','.catalog-tab[aria-current]'],
      ['/events/','#event-category'],['/events/','[data-view="list"]'],
      ['/membership/register/','#association-tab'],['/membership/register/','#pdao-tab'],
      ['/programs/tracking/','main input:not([type=hidden])'],['/accounts/login/','#id_username']
    ];
    const measured=[];let current='';
    for(const [url,selector] of controls){
      if(current!==url){assert.equal(await visit(url),200);current=url;}
      const e=page.locator(selector).first();if(!await e.count()||!await e.isVisible())continue;
      await e.evaluate(n=>n.scrollIntoView({block:'center'}));
      const data=await e.evaluate(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return {x:Math.floor(r.left+r.width*.52),y:Math.floor(r.top)-3,border:s.borderTopColor,kind:s.borderTopStyle};});
      assert.notEqual(data.kind,'none',selector);
      const png=PNG.sync.read(await page.screenshot({animations:'disabled'}));const i=(png.width*data.y+data.x)*4,adjacent=[...png.data.subarray(i,i+3)];
      const contrast=ratio(rgb(data.border),adjacent);measured.push({selector,ratio:Number(contrast.toFixed(2))});if(contrast<3)issues.push([url,selector,'boundary',contrast.toFixed(2),data.border,adjacent]);
    }
    stats.controls=measured.length;stats.minimumBoundary=Math.min(...measured.map(x=>x.ratio));console.log('Control boundaries:',JSON.stringify(measured));
  }else if(mode==='states'){
    const fixturePath=path.resolve('.local/blue-glass-states');
    await page.route(base+'/__glass-check/*',r=>r.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync(path.join(fixturePath,path.basename(new URL(r.request().url()).pathname)+'.html'))}));
    for(const name of ['membership','pdao','submission','request','progress','invalid','forbidden','missing']){
      await visit('/__glass-check/'+name);assert.ok(await page.locator('body.resident-page').count());await fit(page,name);
      assert.ok(await page.locator('main h1').count(),name);await contrast(page,name+' synthetic');
      if(name==='invalid'){assert.ok(await page.locator('[aria-invalid=true]').count());}
      if(name==='membership'||name==='pdao'){
        await page.emulateMedia({media:'print'});assert.ok(await page.locator(name==='membership'?'.association-print-form':'.registration-signature').isVisible());
        assert.ok(!await page.locator('#public-header').isVisible());await page.emulateMedia({media:'screen'});
      }stats.routes++;
    }
    console.log('Synthetic private, receipt, print and error states verified at',width);
  }else if(mode==='staff'){
    const dir=path.resolve('.local/admin-theme-synthetic'),manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json')));
    const entries=new Map(manifest.map(v=>[new URL(v.url,base).pathname+new URL(v.url,base).search,v]));
    await page.route(base+'/**',route=>{const u=new URL(route.request().url()),entry=entries.get(u.pathname+u.search);
      if(entry)return route.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync(path.join(dir,entry.file))});
      if(u.pathname==='/admin/jsi18n/')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.join(dir,'jsi18n.js'))});return route.fallback();});
    for(const name of ['core:dashboard','member_directory','members:detail','members:edit','accounts:password_change','admin:auth_group_add','events:create','programs:create']){
      const entry=manifest.find(v=>v.name===name&&!v.popup);assert.ok(entry,name);
      await visit(entry.url);const body=page.locator('body.admin-workspace');assert.ok(await body.count(),name);assert.equal(await page.locator('link[href*="public-glass"]').count(),0,name);
      for(const theme of ['light','dark']){
        if(await page.locator('html').getAttribute('data-dashboard-theme')!==theme)await page.locator('[data-dashboard-theme-toggle]').click();
        assert.equal(await page.locator('html').getAttribute('data-dashboard-theme'),theme);
        const btn=page.locator('.dashboard-public-link');assert.ok(await btn.isVisible(),name);
        const st=await btn.evaluate(n=>[getComputedStyle(n).color,getComputedStyle(n).backgroundColor]);
        assert.deepEqual(st,['rgb(255, 255, 255)','rgb(25, 81, 252)'],name);await fit(page,name+' '+theme);
        if(['core:dashboard','member_directory','members:detail','accounts:password_change'].includes(name))await contrast(page,name+' '+theme);
        stats.routes++;
      }
    }
    await visit('/accounts/login/');assert.equal(await page.locator('form.account-form button[type=submit]').evaluate(n=>getComputedStyle(n).backgroundColor),'rgb(25, 81, 252)');
    await contrast(page,'staff sign-in');console.log('Verified the staff sign-in and 8 synthetic authenticated layouts in light and dark.');
  }else if(mode==='linked'){
    // Include off-page and past records as well as the first page of each public index.
    const linkSet=new Set(JSON.parse(fs.readFileSync(path.join(output,'links-1440.json'))));
    const indexes=new Set(['/programs/','/events/','/events/?period=past','/announcements/','/results/']);
    for(const list of indexes){
      await visit(list);
      for(const url of await page.locator('main a[href]').evaluateAll(links=>links.map(n=>new URL(n.href)).filter(u=>u.origin===location.origin&&!u.hash).map(u=>u.pathname+u.search))){
        if(/^\/(programs|events|announcements|results)\/(observances\/)?[a-f0-9-]{36}\/$/.test(url))linkSet.add(url);
      }
      for(const url of await page.locator('main [rel=next],.pagination-bar a').evaluateAll(links=>links.map(n=>new URL(n.href)).filter(u=>u.origin===location.origin).map(u=>u.pathname+u.search))){if(!indexes.has(url))indexes.add(url);}
    }
    const links=[...linkSet].filter(x=>!x.includes('/blank-forms/')&&!x.includes('download'));
    const visited=new Set();const deeper=new Set();
    for(const route of [...links,'/accounts/login/','/membership/registration/pdao/apply/']){
      if(visited.has(route)||sections.some(s=>s[1]===route))continue;visited.add(route);
      // Downloads are checked by signature rather than page navigation.
      const response=await page.request.get(base+route);const type=response.headers()['content-type']||'';
      if(type.includes('/pdf')){assert.equal((await response.body()).subarray(0,5).toString(),'%PDF-');continue;}
      const status=await visit(route);if(status!==200&&!(status===503&&route.includes('/pdao/apply/')))issues.push([route,'status',status]);
      await fit(page,route);stats.routes++;if(!await page.locator('link[href*="public-glass.css"]').count())issues.push([route,'missing public theme']);
      const urls=await page.locator('main form[action],main a[href]').evaluateAll(all=>all.map(e=>e.getAttribute('href')||e.getAttribute('action')).filter(s=>s&&/^\/(programs|events|membership|assistance)\/.+\/(verify|apply|register)\/$/.test(s)));urls.forEach(x=>deeper.add(x));
    }
    for(const route of [...deeper].filter(x=>!visited.has(x))){assert.ok([200,503].includes(await visit(route)));await fit(page,route);stats.routes++;}
    console.log('Checked',stats.routes,'linked HTML destinations at',width);
  }
  if(!stats.textSamples)stats.minimumNormal=stats.minimumLarge=null;
  fs.writeFileSync(path.join(output,'checks-'+mode+'-'+width+'.json'),JSON.stringify({stats,issues},null,2));
  console.log(JSON.stringify(stats));if(issues.length){console.error(JSON.stringify(issues.slice(0,25),null,1));process.exitCode=1;}
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
