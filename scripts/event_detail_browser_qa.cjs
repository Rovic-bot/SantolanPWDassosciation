const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT, layouts = [], errors = [], writes = [];
  const cookie = {name:'sessionid',value:process.env.QA_SESSION,url:base};
  try {
    const context = await browser.newContext({viewport:{width:1600,height:1000},reducedMotion:'reduce'});
    await context.addCookies([cookie]);
    await context.route('**/*',route=>{
      const request = route.request(), url = new URL(request.url());
      if(url.origin !== new URL(base).origin) return route.abort();
      if(request.method() !== 'GET') {
        writes.push(url.pathname);
        if(url.pathname !== process.env.QA_DETAIL) return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error=>errors.push(error.message));
    await page.goto(base + process.env.QA_LIST);
    await page.getByRole('link',{name:'Manage Community Wellness Gathering',exact:true}).click();
    assert.equal(new URL(page.url()).pathname,process.env.QA_DETAIL);
    assert.equal(await page.locator('.profile-actions a').getAttribute('href'),process.env.QA_EDIT);
    assert.equal(await page.locator('.event-image-preview img').getAttribute('src'),process.env.QA_IMAGE);
    await page.locator('.event-image-preview img').evaluate(img=>img.decode());
    assert.equal(await page.locator('.event-image-preview img').getAttribute('alt'),'Event image for Community Wellness Gathering');
    assert.equal(await page.locator('.profile-schedule-facts time').count(),2);
    assert.equal(await page.locator('.event-location p').textContent(),'Synthetic Community Hall, Santolan');
    assert.equal(await page.getByRole('link',{name:'View public event',exact:true}).count(),0);
    assert.equal(await page.locator('progress').count(),0,'Do not invent event readiness or attendance counts');
    const history = page.locator('#event-history > summary');
    await history.focus();await page.keyboard.press('Enter');
    await page.waitForFunction(()=>document.querySelector('#event-history > summary').getAttribute('aria-expanded')==='true');
    await page.keyboard.press('Space');
    await page.waitForFunction(()=>document.querySelector('#event-history > summary').getAttribute('aria-expanded')==='false');
    for(const theme of ['dark','light']) {
      if(await page.locator('html').getAttribute('data-dashboard-theme')!==theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for(const width of [1600,1440,1280,1024,768,390,320]) {
        await page.setViewportSize({width,height:1000});
        await page.evaluate(()=>{document.activeElement.blur();scrollTo({top:0,behavior:'instant'});});
        await page.evaluate(()=>document.fonts.ready);
        const metrics = await page.evaluate(()=>{
          const ids = [...document.querySelectorAll('[id]')].map(n=>n.id);
          return {overflow:document.documentElement.scrollWidth>innerWidth+1,duplicates:ids.filter((id,index)=>ids.indexOf(id)!==index)};
        });
        assert.equal(metrics.overflow,false,`${theme}/${width} overflow`);
        assert.deepEqual(metrics.duplicates,[]);
        await assertLayout(page);
        layouts.push({theme,width});
        if([1600,390].includes(width)) await page.screenshot({path:path.join(output,`event-detail-${theme}-${width}.png`),fullPage:true});
      }
    }
    await page.setViewportSize({width:390,height:1000});
    await page.evaluate(()=>{document.documentElement.dataset.text='largest';document.documentElement.dataset.contrast='true';});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.emulateMedia({forcedColors:'active'});
    await history.click();assert.equal(await page.locator('#event-history-content').isVisible(),true);
    await page.emulateMedia({forcedColors:'none'});
    await page.evaluate(()=>{delete document.documentElement.dataset.text;delete document.documentElement.dataset.contrast;});
    await page.setViewportSize({width:1600,height:1000});
    await page.locator('#event-history .pagination-bar').getByRole('link',{name:'Next',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#event-history[open] .pagination-bar')?.textContent.includes('Page 2'));
    assert.match(await page.locator('#event-history .pagination-bar').textContent(),/Page 2/);
    await page.goto(base+process.env.QA_DETAIL);
    await page.locator('#publish-event-form').getByRole('button',{name:'Publish event',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#event-publication-title')?.textContent==='Event published');
    assert.equal(await page.locator('#publish-event-form').count(),0);
    assert.equal(await page.locator('.profile-status').textContent(),'Published');
    await page.evaluate(()=>document.documentElement.dataset.dashboardTheme='dark');
    await page.screenshot({path:path.join(output,'event-detail-published.png'),fullPage:true});
    await page.locator('.profile-status-controls > summary').click();
    await page.locator('#event-status-form [name=action]').selectOption('draft');
    await page.locator('#event-status-form [name=notes]').fill('Synthetic review: return this event to draft.');
    await page.locator('#event-status-form [name=confirm]').check();
    await page.getByRole('button',{name:'Apply event change',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.profile-status')?.textContent==='Draft');
    const fallback = await browser.newContext({javaScriptEnabled:false});await fallback.addCookies([cookie]);
    const plain = await fallback.newPage();await plain.goto(base+process.env.QA_DETAIL);
    await plain.locator('#event-history > summary').click();
    assert.equal(await plain.locator('#event-history-content').isVisible(),true);
    assert.equal(await plain.getByRole('button',{name:'Publish event',exact:true}).isVisible(),true);
    await fallback.close();
    assert.deepEqual(errors,[]);assert.equal(writes.length,2);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({layouts,errors,writes,checks:
      'Manage navigation, shared card layout, dates/venue/full description, protected image, both themes, mobile/desktop, unique IDs, keyboard history/pagination, large text/contrast/forced colors, native fallback and protected publish/withdraw'},null,2));
    console.log(`PASS: ${layouts.length} Event Details layouts; schedule, image, keyboard/history, publication and withdrawal.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

async function assertLayout(page) {
  const box = async selector=>page.locator(selector).boundingBox();
  const layout = await box('.profile-layout'), overview = await box('.profile-overview');
  const publication = await box('.profile-operations'), schedule = await box('.profile-schedule-section');
  const venue = await box('.event-location-section'), image = await box('.event-image-section'), history = await box('.profile-history');
  if(layout.width >= 900) {
    assert.ok(publication.x>=overview.x+overview.width && Math.abs(publication.y-overview.y)<=1);
    assert.ok(venue.x>=schedule.x+schedule.width && Math.abs(venue.y-schedule.y)<=1);
    assert.ok(schedule.width>=venue.width*1.9);
  } else {
    assert.ok(publication.y>=overview.y+overview.height);
    assert.ok(venue.y>=schedule.y+schedule.height);
  }
  assert.ok(schedule.y>=Math.max(overview.y+overview.height,publication.y+publication.height));
  assert.ok(image.y>=Math.max(schedule.y+schedule.height,venue.y+venue.height));
  assert.ok(history.y>=image.y+image.height);
  for(const section of [image,history]) assert.ok(Math.abs(section.x-layout.x)<=1 && Math.abs(section.width-layout.width)<=1);
  assert.ok(await page.locator('.event-image-preview img').evaluate(img=>img.getBoundingClientRect().width<=img.parentElement.clientWidth));
}
