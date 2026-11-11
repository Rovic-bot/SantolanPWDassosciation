/* Read-only contrast inspection of rendered portal text, including photo/gradient backgrounds. */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {PNG} = require('C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/pngjs');
const fs = require('node:fs');
const origin = process.env.QA_URL || 'http://127.0.0.1:8013';
const output = process.env.QA_OUTPUT || '.local/public-dark-contrast-20261109';
const luminance = rgb => rgb.slice(0,3).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum,v,i) => sum + v * [.2126,.7152,.0722][i],0);
function ratio(fg,bg) {const a=luminance(fg),b=luminance(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);}

async function measure(page, name, scope='body') {
  const modal = scope !== 'body';
  const samples = await page.evaluate(({scope,modal}) => {
    const canvas = document.createElement('canvas'), ctx=canvas.getContext('2d',{willReadFrequently:true});
    canvas.width=canvas.height=1;
    const rgb = css => {ctx.clearRect(0,0,1,1);ctx.fillStyle=css;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data];};
    const visible = el => {
      if(!el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) || el.closest('.visually-hidden,[hidden],[inert],script,style,option'))return false;
      if(scope==='body' && el.closest('.portal-navigation,.display-trigger'))return false;
      if(getComputedStyle(el).clipPath==='inset(50%)')return false;
      // Initials underneath a successfully loaded photo are not visible text.
      if(el.matches('.notice-card-initials') && [...el.parentElement.querySelectorAll('img')].some(img=>!img.hidden&&img.complete&&img.naturalWidth))return false;
      return true;
    };
    const selector = el => el.tagName.toLowerCase() + (el.id ? '#'+el.id : '') + [...el.classList].map(c=>'.'+c).join('');
    const items=[];
    function record(el,text,rects,placeholder=false) {
      const style=getComputedStyle(el,placeholder?'::placeholder':null);
      let opacity=Number(style.opacity), ancestor=el.parentElement;
      while(ancestor){opacity*=Number(getComputedStyle(ancestor).opacity);ancestor=ancestor.parentElement;}
      const fg=rgb(style.color);fg[3]*=opacity;
      const boxes=rects.map(r=>({x:r.left,y:r.top,width:r.width,height:r.height})).filter(r=>{
        if(r.width<1||r.height<1||r.x<0||r.x+r.width>innerWidth+1||modal&&(r.y<0||r.y+r.height>innerHeight+1))return false;
        for(let p=el.parentElement;p&&p!==document.body;p=p.parentElement){
          const s=getComputedStyle(p),b=p.getBoundingClientRect();
          // Ignore a line cut by a scrollport edge, where pixels belong to the
          // container border/backdrop. Scroll checks inspect it once fully shown.
          if(/hidden|clip|auto|scroll/.test(s.overflowY)&&(r.y<b.top+parseFloat(s.borderTopWidth)||r.y+r.height>b.bottom-parseFloat(s.borderBottomWidth)))return false;
          if(/hidden|clip|auto|scroll/.test(s.overflowX)&&(r.x<b.left+parseFloat(s.borderLeftWidth)||r.x+r.width>b.right-parseFloat(s.borderRightWidth)))return false;
        }
        return true;
      }).map(r=>({...r,y:r.y+(modal?0:scrollY)}));
      if(boxes.length)items.push({selector:selector(el),text:text.trim().slice(0,110),fg,
        size:parseFloat(style.fontSize),weight:Number(style.fontWeight),boxes,
        required:parseFloat(style.fontSize)>=24||parseFloat(style.fontSize)>=18.66&&Number(style.fontWeight)>=700?3:4.5});
    }
    const root=document.querySelector(scope), walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    let node;
    while(node=walker.nextNode()){
      const el=node.parentElement;
      if(!node.textContent.trim()||!visible(el))continue;
      const range=document.createRange();range.selectNodeContents(node);
      record(el,node.textContent,[...range.getClientRects()]);
    }
    for(const el of root.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]),select,textarea')){
      if(!visible(el))continue;
      const text=el.tagName==='SELECT'?el.selectedOptions[0]?.textContent:el.value||el.placeholder;
      if(!text)continue;
      const r=el.getBoundingClientRect(), s=getComputedStyle(el), font=parseFloat(s.fontSize);
      record(el,text,[{left:r.left+parseFloat(s.paddingLeft)+2,top:r.top+r.height/2-font/2,width:Math.max(1,r.width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-22),height:font}], !el.value&&!!el.placeholder);
    }
    for(const el of root.querySelectorAll('.receipt-qr img,.program-receipt-qr img')){
      if(!visible(el)||!el.complete||el.naturalWidth||!el.alt)continue;
      const r=el.getBoundingClientRect(),font=parseFloat(getComputedStyle(el).fontSize);
      record(el,el.alt,[{left:r.left+20,top:r.top,width:Math.max(1,r.width-22),height:font}]);
    }
    // Hide glyphs without changing layout, so pixel samples capture the actual
    // background beneath text (including gradients, photos and pseudo-elements).
    const elements=[...document.querySelectorAll('body.public-portal *')];
    window.__contrastStyles=elements.map(el=>[el,el.getAttribute('style')]);
    const backgrounds=elements.map(el=>{const s=getComputedStyle(el);return [s.backgroundColor,s.backgroundImage];});
    elements.forEach((el,i)=>{
      el.style.setProperty('background-color',backgrounds[i][0],'important');
      el.style.setProperty('background-image',backgrounds[i][1],'important');
      el.style.setProperty('color','transparent','important');
      el.style.setProperty('-webkit-text-fill-color','transparent','important');
      el.style.setProperty('text-shadow','none','important');
    });
    // Fixed navigation is checked separately. Keep it from covering unrelated
    // document text in a full-page screenshot (especially on narrow screens).
    if(!['.portal-navigation','.display-trigger','.display-panel'].includes(scope))document.querySelectorAll('.portal-navigation,.display-trigger').forEach(el=>el.style.setProperty('visibility','hidden','important'));
    return items;
  },{scope,modal});
  let png;
  try { png=PNG.sync.read(await page.screenshot({fullPage:!modal,animations:'disabled'})); }
  finally {await page.evaluate(()=>{for(const [el,style] of window.__contrastStyles){if(style===null)el.removeAttribute('style');else el.setAttribute('style',style);}delete window.__contrastStyles;});}
  const failures=[];
  for(const sample of samples){
    let min=Infinity, worst;
    for(const r of sample.boxes)for(const dx of [.12,.5,.88])for(const dy of [.25,.75]){
      const x=Math.round(r.x+r.width*dx),y=Math.round(r.y+r.height*dy);
      if(x<0||y<0||x>=png.width||y>=png.height)continue;
      const i=(y*png.width+x)*4,bg=[png.data[i],png.data[i+1],png.data[i+2]],alpha=sample.fg[3]/255;
      const fg=sample.fg.slice(0,3).map((v,index)=>v*alpha+bg[index]*(1-alpha));
      const current=ratio(fg,bg);if(current<min){min=current;worst=bg;}
    }
    if(min<sample.required-.05)failures.push({...sample,ratio:Math.round(min*100)/100,bg:worst});
  }
  return {name,width:page.viewportSize().width,textRuns:samples.length,failures};
}

async function run(){
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const checks=[],errors=[],writes=[];
  try{
    const context=await browser.newContext({reducedMotion:'reduce'});
    const preferences={dark:true,motion:true,...JSON.parse(process.env.QA_PREFERENCES||'{}')};
    await context.addInitScript(preferences=>{try{localStorage.setItem('santolan-display',JSON.stringify(preferences));}catch{/* Sandboxed printable previews cannot access storage. */}},preferences);
    await context.route('**/*',route=>{if(!['GET','HEAD'].includes(route.request().method())){writes.push(route.request().url());return route.abort();}return route.continue();});
    const fixtures=process.env.QA_FIXTURES;
    if(fixtures)await context.route(origin+'/__contrast_fixture/**',route=>route.fulfill({
      contentType:'text/html',body:fs.readFileSync(`${fixtures}/${new URL(route.request().url()).pathname.split('/').pop()}`,'utf8')}));
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    page.setDefaultTimeout(10000);
    const paths=new Set(['/', '/about/', '/announcements/', '/announcements/?category=results', '/events/', '/programs/',
      '/membership/register/', '/resources/', '/contact/', '/information/applications/', '/information/privacy/',
      '/information/accessibility/', '/information/ewaf/', '/information/faq/',
      '/membership/registration/apply/', '/membership/registration/pdao/apply/', '/programs/tracking/',
      '/assistance/referrals/', '/assistance/referrals/verify/']);
    for(const route of ['/programs/','/events/','/announcements/','/resources/']){
      await page.goto(origin+route);
      const links=await page.locator('main a[href]').evaluateAll(es=>es.map(e=>e.getAttribute('href')));
      for(const href of links){if(/^\/(programs|events|events\/observances|announcements)\/[\da-f-]{36}\/$/.test(href)||/^\/resources\/[\w-]+\/$/.test(href))paths.add(href);}
    }
    if(process.env.QA_PATHS){paths.clear();for(const path of JSON.parse(process.env.QA_PATHS))paths.add(path);}
    if(process.env.QA_FIXTURES_ONLY==='1')paths.clear();
    if(fixtures)for(const file of fs.readdirSync(fixtures).filter(f=>f.endsWith('.html')))paths.add('/__contrast_fixture/'+file);
    const widths=(process.env.QA_WIDTHS||'1440,390').split(',').map(Number);
    for(const width of widths){
      await page.setViewportSize({width,height:960});
      for(const path of paths){
        const response=await page.goto(origin+path);if(response.status()!==200){checks.push({name:path,width,status:response.status()});continue;}
        await page.evaluate(()=>document.fonts.ready);
        await page.locator('body.public-portal').waitFor();
        await page.addStyleTag({content:'*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}'});
        if(!path.startsWith('/__contrast_fixture/'))for(const href of await page.locator('main a[href^="/results/"]').evaluateAll(es=>es.map(el=>el.getAttribute('href'))))paths.add(href);
        // Open ordinary reading disclosures; never submit a public form.
        await page.locator('main details:not([data-public-stack-card])').evaluateAll(es=>es.forEach(e=>e.open=true));
        const openDialog=page.locator('dialog[open]');
        if(await openDialog.count()){
          checks.push(await measure(page,path,'dialog[open]'));
          await openDialog.evaluate(el=>el.scrollTop=el.scrollHeight);
          checks.push(await measure(page,path+' lower','dialog[open]'));
        }else checks.push(await measure(page,path));
        if(process.env.QA_INTERACTIONS==='1'){
          const controlRoot=await openDialog.count()?'dialog[open]':'main';
          const controls=await page.locator(`${controlRoot} :is(a,button,summary):visible`).evaluateAll(es=>{
            const seen=new Set();return es.filter(el=>{
              if(el.matches(':disabled')||!el.textContent.trim())return false;
              const key=el.tagName+'.'+[...el.classList].join('.')+(el.hasAttribute('aria-current')?'[current]':'');
              if(seen.has(key))return false;seen.add(key);return true;
            }).map((el,i)=>{el.dataset.contrastControl=String(i);return {id:i,label:el.textContent.trim().slice(0,55)};});
          });
          for(const control of controls){
            const selector=`[data-contrast-control="${control.id}"]`,element=page.locator(selector);
            await element.evaluate(el=>el.scrollIntoView({block:'center'}));
            await element.hover({force:true});
            checks.push(await measure(page,path+' hover '+control.label,selector));
            await page.mouse.move(0,0);await element.focus();
            checks.push(await measure(page,path+' focus '+control.label,selector));
          }
          await page.evaluate(()=>document.activeElement?.blur());await page.evaluate(()=>scrollTo(0,0));
        }
        if(path.startsWith('/__contrast_fixture/'))await page.screenshot({path:`${output}/${path.split('/').pop()}-${width}.png`});
        if(path==='/resources/'||path==='/announcements/'||path==='/programs/')await page.screenshot({path:`${output}/${path.replaceAll('/','')}-${width}.png`});
        if(path==='/announcements/'||path==='/events/'){
          const triggers=page.locator('[data-public-popup]:visible');
          if(await triggers.count()){
            await triggers.first().click();await page.locator('dialog[open] [data-public-popup-content],dialog[open] [data-event-content]').first().waitFor();
            checks.push(await measure(page,path+' popup','dialog[open]'));
            await page.screenshot({path:`${output}/${path.replaceAll('/','')}-popup-${width}.png`});
            await page.keyboard.press('Escape');
          }
        }
        if(path==='/resources/'||path==='/events/'){
          for(const selector of ['[data-concern-open]','[data-tracking-open]','[data-popup-label="Observance details"]']){
            const trigger=page.locator(selector+':visible').first();
            if(!await trigger.count())continue;
            await trigger.click();await page.locator('dialog[open] h2').first().waitFor();
            await page.locator('dialog[open] form,dialog[open] [data-public-popup-content]').first().waitFor();
            checks.push(await measure(page,path+' '+selector,'dialog[open]'));
            if(selector==='[data-concern-open]'&&fixtures){
              const html=fs.readFileSync(`${fixtures}/concern-errors.html`,'utf8');
              await page.locator('dialog[open] [data-concern-body]').evaluate((el,html)=>{
                const main=new DOMParser().parseFromString(html,'text/html').querySelector('main');
                main.querySelectorAll('script,noscript').forEach(el=>el.remove());el.replaceChildren(...main.childNodes);
              },html);
              const dialog=page.locator('dialog[open]'),size=await dialog.evaluate(el=>({height:el.clientHeight,total:el.scrollHeight}));
              for(let offset=0;offset<size.total;offset+=size.height*.7){
                await dialog.evaluate((el,y)=>el.scrollTop=y,offset);
                checks.push(await measure(page,'concern popup validation '+offset,'dialog[open]'));
              }
              await page.screenshot({path:`${output}/concern-validation-${width}.png`});
            }
            if(selector==='[data-concern-open]'||selector==='[data-tracking-open]'){
              await page.locator('dialog[open] [data-concern-notice]').evaluate(el=>{
                el.hidden=false;el.querySelector('[data-concern-error]').textContent='The form could not be loaded. Please try again.';el.scrollIntoView({block:'center'});
              });
              checks.push(await measure(page,path+' loading error '+selector,'dialog[open]'));
            }
            await page.keyboard.press('Escape');
          }
        }
        if(path==='/'){
          checks.push(await measure(page,'main navigation','.portal-navigation'));
          checks.push(await measure(page,'display trigger','.display-trigger'));
          await page.locator('.display-trigger').click();
          checks.push(await measure(page,'display preferences','.display-panel'));
          await page.locator('.display-close').click();
        }
      }
    }
    const summary={checks,errors,writes};fs.writeFileSync(`${output}/contrast.json`,JSON.stringify(summary,null,2));
    console.log(JSON.stringify({pages:checks.length,textRuns:checks.reduce((s,c)=>s+(c.textRuns||0),0),failures:checks.reduce((s,c)=>s+(c.failures?.length||0),0),errors,writes,output}));
    if(process.env.QA_ASSERT==='1'&&(errors.length||writes.length||checks.some(c=>c.status||c.failures?.length)))process.exitCode=1;
  }finally{await browser.close();}
}
if(require.main===module)run().catch(error=>{console.error(error);process.exitCode=1;});
module.exports={measure};
