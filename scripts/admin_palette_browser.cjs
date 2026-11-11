/* Read-only colour/contrast review of disposable, rendered administrator pages. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const fixtures = path.resolve('.local/admin-theme-synthetic');
const output = path.resolve(process.env.PALETTE_OUTPUT || '.local/admin-palette-review');
const base = 'http://127.0.0.1:8013';
async function scan(page) {
  return page.evaluate(() => {
    const canvas=document.createElement('canvas'); canvas.width=canvas.height=1;
    const ctx=canvas.getContext('2d',{willReadFrequently:true}), colors=new Map(), backgrounds=new Map();
    const rgba=value=>{
      if(!colors.has(value)) {ctx.clearRect(0,0,1,1);ctx.fillStyle=value;ctx.fillRect(0,0,1,1);colors.set(value,[...ctx.getImageData(0,0,1,1).data].map((v,i)=>i===3?v/255:v));}
      return colors.get(value);
    };
    const blend=(fg,bg)=>fg.slice(0,3).map((v,i)=>v*(fg[3]??1)+bg[i]*(1-(fg[3]??1)));
    function background(el) {
      if(!el)return [255,255,255];
      if(!backgrounds.has(el)) backgrounds.set(el,blend(rgba(getComputedStyle(el).backgroundColor),background(el.parentElement)));
      return backgrounds.get(el);
    }
    const luminance=c=>c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
    const ratio=(a,b)=>(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
    const elements=new Set(), walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()) if(walker.currentNode.textContent.trim()) elements.add(walker.currentNode.parentElement);
    document.querySelectorAll('input:not([type=hidden]),textarea,select').forEach(el=>elements.add(el));
    const low=[], seen=new Set(); let checked=0;
    for(const el of elements) {
      if(el.closest('script,style,noscript,progress,.visually-hidden,.sr-only,[hidden],[aria-hidden=true]')||!el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}))continue;
      const rect=el.getBoundingClientRect(); if(rect.width<2||rect.height<2)continue;
      const css=getComputedStyle(el), value=el instanceof SVGElement?css.fill:
        (el.matches('input,textarea')&&!el.value&&el.placeholder?getComputedStyle(el,'::placeholder').color:css.color);
      if(parseFloat(css.textIndent)<-rect.width)continue; // Native icon buttons have off-screen accessible names.
      let bg=background(el);
      if(el instanceof SVGTextElement && el.getAttribute('fill')==='var(--chart-label)') {
        // Numbered pie/donut labels sit on SVG slices, not the HTML card background.
        const svg=el.ownerSVGElement, point=new DOMPoint(Number(el.getAttribute('x')),Number(el.getAttribute('y')));
        for(const shape of svg.querySelectorAll('path,circle,rect')) {
          if(shape.isPointInFill?.(point) && getComputedStyle(shape).fill!=='none') bg=blend(rgba(getComputedStyle(shape).fill),bg);
        }
      }
      if(value==='none')continue;
      let opacity=1;for(let p=el;p;p=p.parentElement)opacity*=Number(getComputedStyle(p).opacity);
      const fg=rgba(value);const painted=blend([fg[0],fg[1],fg[2],fg[3]*opacity],bg);
      const contrast=ratio(painted,bg), large=parseFloat(css.fontSize)>=24||(parseFloat(css.fontSize)>=18.66&&parseInt(css.fontWeight)>=700);
      checked++;
      if(contrast<(large?3:4.5)) {
        const selector=el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+(typeof el.className==='string'&&el.className?'.'+el.className.trim().replace(/\s+/g,'.'):'');
        const key=selector+'|'+value+'|'+bg.join();if(seen.has(key))continue;seen.add(key);
        low.push({selector,text:String(el.value||el.textContent).trim().slice(0,60),ratio:+contrast.toFixed(2),foreground:value,background:bg.map(Math.round),image:css.backgroundImage});
      }
    }
    return {checked,low};
  });
}
module.exports = {scan};
if(require.main===module)(async()=>{
  const manifest = JSON.parse(fs.readFileSync(path.join(fixtures,'manifest.json'),'utf8'));
  const selected = process.env.PALETTE_PAGES ? manifest.filter(row=>process.env.PALETTE_PAGES.split(',').includes(row.name)) : manifest;
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const byURL=new Map(manifest.map(row=>[row.url,row]));
  await context.route('**/*',route=>{
    const req=route.request(),url=new URL(req.url());
    if(req.method()!=='GET')return route.abort();
    const fixture=byURL.get(url.pathname+url.search);
    if(fixture&&url.origin===base)return route.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync(path.join(fixtures,fixture.file))});
    if(url.pathname==='/admin/jsi18n/')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.join(fixtures,'jsi18n.js'))});
    if(url.origin===base&&url.pathname.startsWith('/static/'))return route.continue();
    return route.fulfill({status:404,body:'Outside the synthetic fixture'});
  });
  const page=await context.newPage(), errors=[], findings=[], checks=[];
  page.on('pageerror',error=>errors.push(error.message));
  try {
    await page.goto(base+manifest[0].url);
    for(const [index,entry] of selected.entries()) {
      for(const theme of ['light','dark','contrast']) {
        await page.setViewportSize({width:1440,height:1000});
        await page.evaluate(theme=>{
          localStorage.setItem('santolan-dashboard-theme',theme==='light'?'light':'dark');
          localStorage.setItem('santolan-display',JSON.stringify({contrast:theme==='contrast',motion:true}));
        },theme);
        await page.goto(base+entry.url,{waitUntil:'load'});
        if(entry.popup)await page.evaluate(theme=>document.documentElement.dataset.contrast=String(theme==='contrast'),theme);
        assert.equal(await page.locator('link[href*="admin-palette.css"]').count(),1,entry.name);
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        for(const width of [1440,390]) {
          await page.setViewportSize({width,height:1000});
          await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
          const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
          const result=await scan(page);
          if(result.low.length)findings.push({name:entry.name,file:entry.file,theme,width,...result});
          checks.push({name:entry.name,theme,width,overflow,checkedText:result.checked});
          if(['core:dashboard','member_directory','program_portfolio','programs:create','membership:encode','admin:admin_logentry_changelist','admin:auth_user_change'].includes(entry.name))
            await page.screenshot({path:path.join(output,`${entry.file.slice(0,-5)}-${theme}-${width}.png`)});
        }
      }
      if(index%10===0)console.log(`Checked ${index+1}/${selected.length} screens`);
      fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({pages:index+1,errors,findings,checks},null,2));
    }
    console.log(JSON.stringify({pages:selected.length,checks:checks.length,lowContrastScreens:findings.length,overflow:checks.filter(x=>x.overflow).length,errors}));
    assert.deepEqual(errors,[],'JavaScript errors');
    assert.deepEqual(findings,[],'Visible text contrast; see results.json');
    assert.equal(checks.filter(x=>x.overflow).length,0,'Horizontal overflow');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
