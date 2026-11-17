/* Fictional loopback conversations only. No production writes or email delivery. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = path.resolve(process.env.OPTIMISTIC_SOURCE || path.join(__dirname,'..'));
const output = path.resolve(process.env.OPTIMISTIC_OUTPUT || '.local/optimistic-feedback-qa');
const assetDirectory = process.env.OPTIMISTIC_ASSETS && path.resolve(process.env.OPTIMISTIC_ASSETS);
fs.mkdirSync(output,{recursive:true});
const checks=[], errors=[], posts=[];
let base, state, pending, arriving;
const reset = () => { state={version:1,messages:[]}; };
const payload = () => ({ticket:'fictional',version:state.version,status:'Open',status_code:'pending',closed:false,
  can_review:true,sender_version:1,sender_email:'office@example.invalid',messages:state.messages,
  activity_html:'<ol data-referral-activity></ol>',email_revision:String(state.version),
  email_html:'<details class="referral-email-history"><summary>Email history</summary></details>'});
const shell = kind => {
  const staff=kind==='staff';
  const conversation=staff?`<article data-referral-ticket="fictional" data-version="1" data-updates-url="/updates/" data-channel-key="fictional-channel" data-member-name="Example member">
    <header class="referral-ticket-header"><h1>Community Assistance Desk</h1><span class="referral-status">Open</span></header>
    <div class="referral-conversation"></div><ol data-referral-activity></ol>
    <form data-referral-reply method="post" action="/send/staff/"><input type="hidden" name="version" value="1"><input type="hidden" name="sender_version" value="1">
      <input type="hidden" name="csrfmiddlewaretoken" value="fictional-csrf"><label for="message">Reply to member</label><textarea id="message" name="member_message" required></textarea>
      <label for="channel">Send through</label><select id="channel" name="channel"><option value="email">Email</option><option value="online">Online conversation</option></select>
      <button type="submit" data-reply-submit>Send reply</button><p data-referral-live-notice role="status"></p></form></article>`:
    `<section data-referral-conversation data-ticket="fictional" data-version="1" data-updates-url="/updates/" data-new-concern-url="/public/">
    <h1>My conversation</h1><span data-conversation-status>Open</span><div data-conversation-messages class="concern-chat-messages" role="log"></div>
    <p data-conversation-notice role="status"></p><form data-conversation-form method="post" action="/send/public/">
    <input type="hidden" name="csrfmiddlewaretoken" value="fictional-csrf"><input type="hidden" name="version" value="1">
    <label for="message">Your message</label><textarea id="message" name="message" required></textarea><button type="submit">Send message</button></form></section>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    ${['tokens','site','public-conversations','referral-ticket','action-feedback'].map(name=>`<link rel="stylesheet" href="/static/css/${name}.css">`).join('')}
    <style>body{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,sans-serif}main{max-width:800px;margin:40px auto;padding:16px}h1{font-size:1.6rem}form{display:grid;gap:12px;margin-top:20px}textarea{width:100%;min-height:90px;padding:12px;box-sizing:border-box}button,select{padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}.referral-conversation{height:240px;overflow:auto;display:flex;flex-direction:column;gap:16px;padding:16px;border:1px solid var(--line)}.concern-chat-messages{min-height:160px}dialog{max-width:calc(100vw - 48px);background:var(--surface);color:var(--ink)}html[data-contrast=true] body{--paper:#fff;--surface:#fff;--ink:#111;--line:#111;--control-edge:#111}</style>
    <script src="/static/js/workspace-page.js"></script><script src="/static/js/action-feedback.js" defer></script>
    <script src="/static/js/${staff?'referral-live':'public-conversations'}.js" defer></script></head>
    <body class="${staff?'':'public-portal'}"><main id="main-content">${conversation}</main>
    <dialog id="test-dialog"><form id="dialog-form" method="dialog"><p>Email preview</p><button type="button">Retry email</button></form></dialog></body></html>`;
};
const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url,base||'http://127.0.0.1');
  if(url.pathname.startsWith('/static/')){
    const relative=url.pathname.slice(1),file=path.resolve(root,relative);
    const override=assetDirectory&&path.resolve(assetDirectory,relative);
    const selected=override&&fs.existsSync(override)?override:file;
    if(!file.startsWith(path.join(root,'static')+path.sep)||!fs.existsSync(selected)){res.writeHead(404);return res.end();}
    res.writeHead(200,{'content-type':file.endsWith('.js')?'application/javascript; charset=utf-8':'text/css; charset=utf-8'});return res.end(fs.readFileSync(selected));
  }
  if(req.method==='POST'){
    let body='';for await(const chunk of req)body+=chunk;
    posts.push({path:url.pathname,body});pending={res,body,kind:url.pathname.includes('staff')?'staff':'public'};
    arriving?.();arriving=undefined;return;
  }
  if(url.pathname==='/updates/'){res.writeHead(200,{'content-type':'application/json'});return res.end(JSON.stringify(payload()));}
  res.writeHead(200,{'content-type':'text/html; charset=utf-8'});res.end(shell(url.pathname.includes('staff')?'staff':'public'));
});
async function received(){if(pending)return;await new Promise(resolve=>{arriving=resolve;});}
function resolveSend(mode,text){
  assert.ok(pending);const {res,kind}=pending;pending=undefined;
  if(mode==='forbidden'){res.writeHead(403,{'content-type':'application/json'});res.end('{}');return;}
  const data=payload();
  if(mode!=='reject'){
    state.version++;state.messages.push({id:state.version,sender:kind==='staff'?'staff':'member',message:text,recorded_at:'2026-11-17T01:00:00Z'});
    Object.assign(data,payload(),{sent:true,notice:mode==='delivery-error'?'Reply saved. The email service did not accept this email.':'Email accepted by the email service.',delivery_error:mode==='delivery-error'});
  }else Object.assign(data,{sent:false,errors:['This request was rejected. Your draft is kept.']});
  if(mode==='disconnect'){
    res.writeHead(200,{'content-type':'application/json','content-length':'9000'});
    res.write('{');setTimeout(()=>res.destroy(),20);return;
  }
  res.writeHead(mode==='reject'?400:200,{'content-type':'application/json'});res.end(JSON.stringify(data));
}
const pass=(name,detail)=>{checks.push({name,detail});console.log('PASS',name);};
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));base=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:960}});page.setDefaultTimeout(10000);
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
    const visit=async kind=>{reset();await page.goto(base+'/'+kind+'/');await page.waitForFunction(()=>!!window.ActionFeedback);};
    const send=async text=>{await page.locator('#message').fill(text);await page.locator('main button[type=submit]').click();await received();};
    const settled=()=>page.waitForFunction(()=>!document.querySelector('[data-pending-message], .action-status-card'));
    const notice=()=>page.locator('[data-referral-live-notice], [data-conversation-notice]');
    const text='Please bring the requested document to the Help Desk. <img src=x onerror=alert(1)>';

    for(const kind of ['staff','public']){
      await visit(kind);const count=posts.length;await send(text);
      assert.equal(await page.locator('[data-pending-message]').count(),1);
      assert.equal(await page.locator('[data-pending-message] img').count(),0);
      assert.match(await page.locator('[data-pending-message]').innerText(),/Sending (email|message)/);
      assert.equal(await page.locator('[data-message-id]').count(),0);
      assert.equal(await page.locator('.action-status-card').count(),1);
      assert.equal(await page.locator('.action-status-tray').evaluate(el=>el.matches(':popover-open')),true);
      assert.equal(await page.locator('.action-loading-bar').isVisible(),true);
      await page.evaluate(()=>document.querySelector('main form').requestSubmit());
      assert.equal(posts.length,count+1);
      await page.screenshot({path:path.join(output,kind+'-pending-desktop.png')});
      pass(kind+' immediate pending message is text-only and blocks duplicate sends');
      resolveSend('success',text);await settled();
      assert.equal(await page.locator('[data-message-id]').count(),1);
      assert.equal(await page.locator('#message').inputValue(),'');
      assert.equal(await page.locator('.action-loading-bar').isVisible(),false);
      assert.match(posts.at(-1).body,/fictional-csrf/);
      pass(kind+' replaces preview with one server-confirmed message');

      await visit(kind);await send('Draft that must survive rejection.');resolveSend('reject');await settled();
      assert.equal(await page.locator('#message').inputValue(),'Draft that must survive rejection.');
      assert.equal(await page.locator('[data-message-id]').count(),0);
      assert.match(await notice().innerText(),/rejected/);
      assert.equal(await page.locator('main button[type=submit]').isEnabled(),true);
      pass(kind+' rejected request rolls back preview and keeps the draft');

      await visit(kind);const before=posts.length;await send('Draft after interrupted response.');resolveSend('disconnect','Draft after interrupted response.');await settled();
      assert.match(await notice().innerText(),/Could not confirm/);
      assert.equal(await page.locator('#message').inputValue(),'Draft after interrupted response.');
      await page.waitForFunction(()=>!!document.querySelector('[data-message-id]'));
      assert.equal(posts.length,before+1);
      assert.equal(await page.locator('main [name=version]').inputValue(),'1');
      pass(kind+' lost response keeps the draft and original retry revision without replaying a write');
    }
    await visit('staff');await send('Reply with failed email delivery.');resolveSend('delivery-error','Reply with failed email delivery.');await settled();
    assert.equal(await page.locator('[data-message-id]').count(),1);assert.match(await notice().innerText(),/did not accept/);
    assert.equal(await notice().getAttribute('data-error'),'true');
    pass('saved reply and failed email delivery remain distinct');
    await visit('public');await send('Draft retained when access expires.');resolveSend('forbidden');await settled();
    assert.equal(await page.locator('[data-message-id], [data-pending-message]').count(),0);
    assert.equal(await page.locator('main button[type=submit]').isDisabled(),true);
    assert.equal(await page.locator('#message').inputValue(),'Draft retained when access expires.');
    pass('expired private access clears the preview and disables further sends');

    await visit('staff');
    await page.evaluate(()=>{const d=document.querySelector('dialog');d.showModal();const b=d.querySelector('button');b.focus();window.finish=ActionFeedback.start(d.querySelector('form'),{button:b,label:'Sending email…'});});
    assert.equal(await page.locator('.action-status-tray').evaluate(el=>el.matches(':popover-open')),true);
    assert.equal(await page.evaluate(()=>document.activeElement===document.querySelector('dialog button')),true);
    await page.screenshot({path:path.join(output,'modal-pending.png')});
    await page.evaluate(()=>{window.finish();document.querySelector('dialog').close();});
    pass('pending status stays above modal dialogs without taking keyboard focus');

    for(const width of [390,320]){
      await page.setViewportSize({width,height:844});await visit('staff');await send('A fictional email for the mobile preview.');
      for(const mode of ['light','dark','contrast']){
        await page.evaluate(mode=>{document.documentElement.dataset.dashboardTheme=mode==='dark'?'dark':'light';document.documentElement.dataset.contrast=String(mode==='contrast');
          document.body.style.setProperty('--surface',mode==='dark'?'#242220':'#f4f2ec');document.body.style.setProperty('--paper',mode==='dark'?'#191817':'#e8e5df');document.body.style.setProperty('--ink',mode==='dark'?'#f4f2ec':'#1c1a18');},mode);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
        const rect=await page.locator('.action-status-card').boundingBox();assert.ok(rect.x>=0&&rect.x+rect.width<=width);
        await page.screenshot({path:path.join(output,`pending-${mode}-${width}.png`)});
      }
      resolveSend('success','A fictional email for the mobile preview.');await settled();pass('responsive pending status at '+width+' px in light, dark and high contrast');
    }
    await visit('staff');await page.locator('main').evaluate(el=>el.setAttribute('aria-busy','true'));
    assert.equal(await page.locator('.action-loading-bar').isVisible(),true);
    await page.emulateMedia({reducedMotion:'reduce'});
    assert.equal(await page.locator('.action-loading-bar').evaluate(el=>getComputedStyle(el,'::after').animationName),'none');
    await page.locator('main').evaluate(el=>el.removeAttribute('aria-busy'));assert.equal(await page.locator('.action-loading-bar').isVisible(),false);
    pass('read-only loading bar follows existing busy states and reduced motion');
    await page.evaluate(()=>{const form=document.querySelector('main form');window.one=ActionFeedback.start(form);window.two=ActionFeedback.start(form);window.one();});
    assert.equal(await page.locator('.action-status-card').count(),1);await page.evaluate(()=>window.two());await settled();
    pass('overlapping requests share one pending card until both finish');
    await page.evaluate(()=>{ActionFeedback.start(document.querySelector('main form'));ActionFeedback.previewMessage(document.querySelector('.referral-conversation'),{text:'Private fictional draft'});WorkspacePage.replace();});
    assert.equal(await page.locator('.action-status-tray, .action-loading-bar, [data-pending-message]').count(),0);
    pass('workspace disposal removes pending UI and private message previews');
    assert.deepEqual(errors,[]);console.log(JSON.stringify({checks:checks.length,errors,syntheticPosts:posts.length}));
  }finally{fs.writeFileSync(path.join(output,'checks.json'),JSON.stringify({checks,errors,syntheticPosts:posts.length},null,2));pending?.res.destroy();pending=undefined;await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;pending?.res.destroy();server.close();});
