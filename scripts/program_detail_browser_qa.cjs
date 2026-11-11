const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, url = base + process.env.QA_PROFILE_ROUTE, output = process.env.QA_OUTPUT;
  const cookie = {name:'sessionid', value:process.env.QA_ADMIN_SESSION, url:base};
    const errors = [], layouts = [], popupLayouts = [], writes = [];
  try {
    const context = await browser.newContext({viewport:{width:1600,height:1000}, reducedMotion:'reduce', colorScheme:'dark'});
    await context.addCookies([cookie]);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    // Only these synthetic detail forms may write; unexpected writes are rejected.
    await context.route(base+'/**', route => {
      if(route.request().method() !== 'GET') {
        const destination = new URL(route.request().url()).pathname;
        writes.push(destination);
        if(!['/admin/programs/detail',process.env.QA_PROFILE_LEGACY,process.env.QA_BLOCKED_ROUTE].includes(destination)) return route.abort();
      }
      return route.continue();
    });
    await page.goto(url);
    assert.equal(await page.locator('a[aria-current=page]').textContent(), 'Program Management');
    assert.equal(await page.locator('.profile-lifecycle, .profile-readiness-count, #program-selection-title').count(), 0);
    assert.equal(await page.locator('.profile-metrics, .profile-timezone').count(), 0);
    assert.equal(await page.locator('.profile-actions a').filter({hasText:'Review applications'}).getAttribute('href'), process.env.QA_REVIEW_ROUTE);
    const history = page.locator('#program-history > summary');
    await history.focus();await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#program-history > summary').getAttribute('aria-expanded') === 'true');
    assert.ok(await page.locator('#program-history .record-history').count());
    await page.keyboard.press('Space');
    await page.waitForFunction(() => document.querySelector('#program-history > summary').getAttribute('aria-expanded') === 'false');
    for(const theme of ['dark','light']) {
      if(await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for(const width of [1600,1440,1280,1024,768,390,320]) {
        await page.setViewportSize({width,height:1000});
        await page.evaluate(() => scrollTo({top:0,behavior:'instant'}));
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1), true, `${theme}/${width}: overflow`);
        const duplicates = await page.evaluate(() => {const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);return ids.filter((id,i)=>ids.indexOf(id)!==i);});
        assert.deepEqual(duplicates, []);
        await assertProfileLayout(page);
        if(width>=1280) assert.equal(await page.locator('.profile-header h1').evaluate(node => {
          const range = document.createRange(); range.selectNodeContents(node);
          return new Set([...range.getClientRects()].map(box => Math.round(box.top))).size;
        }), 1, 'Program title stays on one desktop line');
        layouts.push({theme,width});
        if([1600,390].includes(width)) {
          await page.evaluate(async () => {for(let y=0;y<document.documentElement.scrollHeight;y+=innerHeight){scrollTo({top:y,behavior:'instant'});await new Promise(requestAnimationFrame);}scrollTo({top:0,behavior:'instant'});});
          await page.screenshot({path:path.join(output,`program-detail-${theme}-${width}.png`),fullPage:true});
        }
      }
      await page.setViewportSize({width:1440,height:1000});
      await page.locator('.profile-layout').evaluate(n => scrollTo({top:n.getBoundingClientRect().top+scrollY+180,behavior:'instant'}));
      assert.equal(await page.locator('.profile-operations').evaluate(n=>getComputedStyle(n).overflowY),'visible');
      await page.locator('.profile-publish-button').scrollIntoViewIfNeeded();
      const action = await page.locator('.profile-publish-button').boundingBox();
      assert.ok(action.y >= 76 && action.y + action.height <= 1000, 'Publication action remains accessible');
      await page.screenshot({path:path.join(output,`program-detail-publication-${theme}.png`)});
    }
    await page.reload();assert.equal(await page.locator('html').getAttribute('data-dashboard-theme'),'light');
    await page.setViewportSize({width:390,height:1000});
    await page.evaluate(() => {document.documentElement.dataset.text='largest';document.documentElement.dataset.contrast='true';});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth+1),true);
    await page.emulateMedia({forcedColors:'active'});await history.click();
    assert.equal(await page.locator('#program-history-content').isVisible(),true);
    await page.emulateMedia({forcedColors:'none'});
    await page.evaluate(() => {delete document.documentElement.dataset.text;delete document.documentElement.dataset.contrast;});
    const fallbackContext=await browser.newContext({javaScriptEnabled:false});await fallbackContext.addCookies([cookie]);
    const fallback=await fallbackContext.newPage();await fallback.goto(url);await fallback.locator('#program-history > summary').click();
    assert.equal(await fallback.locator('#program-history-content').isVisible(),true);
    await fallback.goto(base+process.env.QA_PORTFOLIO_ROUTE);
    await fallback.getByRole('link',{name:'Medical Access Week',exact:true}).click();
    assert.equal(new URL(fallback.url()).pathname,process.env.QA_PROFILE_LEGACY);
    await fallbackContext.close();

    // Open from the filtered board; details and history stay inside the popup.
    await page.goto(base+process.env.QA_PORTFOLIO_ROUTE);
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('#program-search').fill('Medical');
    await page.waitForFunction(()=>document.querySelector('[data-portfolio-count]').textContent==='1');
    const portfolioUrl=page.url();
    const opener=page.locator('.portfolio-program footer [data-program-dialog]').first();
    const popup=page.locator('#program-details-dialog');
    const openProgram=async()=>{
      await opener.click();
      await popup.locator('[data-program-profile] h1').waitFor();
      assert.equal(page.url(),portfolioUrl);
      assert.match(await popup.locator('h1').textContent(),/Medical Access Week/);
      assert.equal(await popup.locator('.profile-metrics, .profile-timezone').count(),0);
    };
    for(const theme of ['dark','light']) {
      if(await page.locator('html').getAttribute('data-dashboard-theme')!==theme)await page.locator('[data-dashboard-theme-toggle]').click();
      await openProgram();
      for(const width of [1600,1280,1024,768,390,320]) {
        await page.setViewportSize({width,height:900});
        const box=await popup.boundingBox();
        assert.ok(box.x>=0 && box.y>=0 && box.x+box.width<=width && box.y+box.height<=900);
        assert.ok(box.width<=1120, 'Popup stays within the compact desktop maximum width');
        if(width>=640)assert.ok(box.x>=39 && box.y>=31, 'Desktop popup leaves space around the workspace');
        await assertProfileLayout(popup);
        assert.equal(await popup.locator('[data-program-dialog-content]').evaluate(n=>n.scrollWidth<=n.clientWidth+1),true,`popup ${theme}/${width} overflow`);
        assert.equal(await popup.locator('[data-program-dialog-close]').isVisible(),true);
        popupLayouts.push({theme,width});
        if([1600,390].includes(width))await page.screenshot({path:path.join(output,`program-dialog-${theme}-${width}.png`)});
      }
      await page.setViewportSize({width:1440,height:1000});
      await popup.locator('#program-history > summary').click();
      await popup.locator('.pagination-bar').getByRole('link',{name:'Next',exact:true}).click();
      await popup.locator('#program-history[open]').waitFor();
      assert.match(await popup.locator('.pagination-bar').textContent(),/Page 2/);
      assert.equal(page.url(),portfolioUrl);
      for(let i=0;i<16;i++) {
        await page.keyboard.press('Tab');
        const focus=await popup.evaluate(node=>({inside:node.contains(document.activeElement),active:document.activeElement.outerHTML.slice(0,180)}));
        assert.equal(focus.inside,true,`Focus stays inside the popup at tab ${i}: ${focus.active}`);
      }
      await page.keyboard.press('Escape');
      assert.equal(await popup.isVisible(),false);
      assert.equal(await opener.evaluate(node=>node===document.activeElement),true);
      assert.equal(await page.locator('#program-search').inputValue(),'Medical');
    }
    await page.route(base+process.env.QA_PROFILE_LEGACY,route=>route.fulfill({status:503,body:'Unavailable'}));
    await opener.click();await popup.getByRole('alert').waitFor();
    assert.equal(page.url(),portfolioUrl);
    await page.unroute(base+process.env.QA_PROFILE_LEGACY);
    await popup.getByRole('button',{name:'Reload details'}).click();
    await popup.locator('[data-program-profile] h1').waitFor();
    await page.mouse.click(2,2);
    assert.equal(await popup.isVisible(),false,'Backdrop closes the popup');
    // An aborted load must not reopen or populate a closed popup.
    await page.route(base+process.env.QA_PROFILE_LEGACY,async route=>{await new Promise(resolve=>setTimeout(resolve,350));return route.continue();});
    await opener.click();await popup.getByRole('button',{name:'Close program details'}).click();
    await page.waitForTimeout(400);assert.equal(await popup.isVisible(),false);
    await page.unroute(base+process.env.QA_PROFILE_LEGACY);
    await openProgram();
    assert.equal(await popup.locator('[data-program-full-page]').getAttribute('href'),base+process.env.QA_PROFILE_LEGACY);

    // Real protected forms remain in the popup and refresh the underlying card.
    await page.locator('.profile-publish-button').click();
    await page.waitForFunction(()=>document.querySelector('#program-details-dialog #program-publication-title')?.textContent==='Program is live' || document.querySelector('#program-details-dialog [role=alert]'));
    assert.equal(await popup.locator('[role=alert]').count(),0,await popup.locator('[role=alert]').allTextContents());
    assert.equal(page.url(),portfolioUrl);
    assert.equal(await page.locator('.profile-status').textContent(),'Published');
    assert.equal(await page.locator('#program-publication-title').textContent(),'Program is live');
    assert.equal(await popup.locator('[data-capacity-available]').textContent(),'2 unallocated');
    assert.match(await popup.locator('.profile-quick-facts').textContent(),/3 applications/);
    await page.setViewportSize({width:1600,height:1000});
    for(const theme of ['dark','light']) {
      // The toolbar theme button is behind the modal; use its existing theme state for the visual check.
      await page.evaluate(theme=>document.documentElement.dataset.dashboardTheme=theme,theme);
      await popup.locator('[data-program-dialog-content]').evaluate(n=>n.scrollTop=0);
      await page.screenshot({path:path.join(output,`program-dialog-published-${theme}.png`)});
      await popup.locator('#requirements').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(output,`program-dialog-requirements-${theme}.png`)});
    }
    await page.locator('.profile-status-controls > summary').click();
    await page.locator('#program-status-form [name=action]').selectOption('draft');
    await page.locator('#program-status-form [name=notes]').fill('Synthetic review: return this demonstration program to a private draft.');
    await page.locator('#program-status-form [name=confirm]').check();
    await page.getByRole('button',{name:'Apply program change',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#program-details-dialog .profile-status')?.textContent==='Draft');
    assert.equal(await page.locator('.profile-status').textContent(),'Draft');
    await popup.getByRole('button',{name:'Close program details'}).click();
    await page.waitForFunction(()=>document.querySelector('.portfolio-program .portfolio-status')?.textContent==='Draft' && !document.querySelector('[data-portfolio-results]').hasAttribute('aria-busy'));
    assert.equal(page.url(),portfolioUrl);
    await page.goto(base+process.env.QA_APPLICATION_ROUTE+'?q=Assistive');
    const applicationUrl=page.url();
    await page.locator('[data-preview-detail]').click();
    await popup.locator('[data-program-profile] h1').waitFor();
    assert.match(await popup.locator('h1').textContent(),/Assistive Device Distribution/);
    await page.screenshot({path:path.join(output,'program-dialog-applications.png')});
    await page.locator('.profile-publish-button').click();
    await page.locator('#publish-program-form [role=alert]').waitFor();
    assert.equal(await page.locator('.profile-status').textContent(),'Draft');
    assert.ok((await page.locator('.profile-requirements-empty').boundingBox()).width>250);
    assert.equal(await page.locator('#publish-program-form [role=alert]').evaluate(n=>n===document.activeElement),true);
    assert.equal(page.url(),applicationUrl);
    assert.deepEqual(errors,[]);assert.equal(writes.length,3);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({layouts,popupLayouts,errors,writes,
      checks:'Direct detail and modal layouts, both entry points, filtered context preserved, keyboard/focus trap/Escape/backdrop, history pagination, failed/aborted loads and retry, no-JS, real popup publication/withdrawal, background refresh and blocked EWAF error'},null,2));
    console.log(`PASS: ${layouts.length} page and ${popupLayouts.length} popup layouts; modal navigation, history, publication, withdrawal and blocked EWAF checks.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

async function assertProfileLayout(root) {
  const layout = await root.locator('.profile-layout').boundingBox();
  const overview = await root.locator('.profile-overview').boundingBox();
  const publication = await root.locator('.profile-operations').boundingBox();
  const schedule = await root.locator('.profile-schedule-section').boundingBox();
  const eligibility = await root.locator('.profile-eligibility-section').boundingBox();
  const requirements = await root.locator('.profile-requirements-section').boundingBox();
  const history = await root.locator('.profile-history').boundingBox();
  if (layout.width >= 900) {
    assert.ok(publication.x >= overview.x + overview.width, 'Publication sits beside the overview');
    assert.ok(Math.abs(publication.y - overview.y) <= 1, 'Overview and publication share the first row');
    assert.ok(Math.abs(publication.height - overview.height) <= 1, 'Overview and publication fill the same row height');
    assert.ok(eligibility.x >= schedule.x + schedule.width, 'Eligibility sits beside the schedule');
    assert.ok(Math.abs(eligibility.y - schedule.y) <= 1, 'Schedule and eligibility share the second row');
    assert.ok(Math.abs(schedule.width - overview.width) <= 1, 'Left-column cards align');
    assert.ok(Math.abs(eligibility.width - publication.width) <= 1, 'Right-column cards align');
    assert.ok(schedule.width >= eligibility.width * 1.9, 'The left column uses two thirds of the card area');
    assert.ok(Math.abs(requirements.x - schedule.x) <= 1 && Math.abs(requirements.width - schedule.width) <= 1, 'Requirements align with the left column');
    assert.ok(requirements.y >= schedule.y + schedule.height && requirements.y <= schedule.y + schedule.height + 24, 'Requirements sit directly below the schedule');
  } else {
    assert.ok(publication.y >= overview.y + overview.height, 'Publication follows the overview on smaller screens');
    assert.ok(eligibility.y >= schedule.y + schedule.height, 'Eligibility follows the schedule on smaller screens');
    assert.ok(requirements.y >= eligibility.y + eligibility.height, 'Requirements follow eligibility on smaller screens');
    assert.ok(Math.abs(requirements.x - layout.x) <= 1 && Math.abs(requirements.width - layout.width) <= 1, 'Requirements use the full width on smaller screens');
  }
  assert.ok(schedule.y >= Math.max(overview.y + overview.height, publication.y + publication.height), 'Schedule follows the first row');
  assert.ok(history.y >= Math.max(requirements.y + requirements.height, eligibility.y + eligibility.height), 'History follows both columns');
  assert.ok(Math.abs(history.x - layout.x) <= 1 && Math.abs(history.width - layout.width) <= 1, 'History uses the full width');
  const tiles = await root.locator('.profile-requirements > li').all();
  const columns = layout.width >= 600 ? 2 : 1;
  const first = await tiles[0].boundingBox();
  for (let i = 1; i < tiles.length; i++) {
    const tile = await tiles[i].boundingBox();
    if (i < columns) assert.ok(Math.abs(tile.y - first.y) <= 1, 'Requirement tiles share a row');
    else assert.ok(tile.y >= first.y + first.height, 'Additional requirements wrap into rows');
  }
}
