const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, route = process.env.QA_CREATE_ROUTE, output = process.env.QA_OUTPUT;
  const cookie = {name:'sessionid', value:process.env.QA_ADMIN_SESSION, url:base};
  const layouts = [], errors = [], posts = [];
  const allowedPosts = new Set([route]);
  try {
    const context = await browser.newContext({viewport:{width:1600,height:1000}, reducedMotion:'reduce'});
    await context.addCookies([cookie]);
    await context.route(base+'/**', request => {
      if (request.request().method() !== 'GET') {
        assert.ok(allowedPosts.has(new URL(request.request().url()).pathname));
        posts.push(request.request().url());
      }
      return request.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await page.goto(base+route);
    await page.locator('.builder-range-picker').waitFor({state:'visible'});
    assert.equal(await page.locator('a[aria-current=page]').textContent(), 'Events Calendar');
    assert.equal(await page.locator('.builder-calendar').count(), 1);
    assert.equal(await page.locator('[data-apply-range], [data-clear-range]').count(), 0);
    const fields = await page.locator('[data-event-form] [name]').evaluateAll(nodes => nodes.map(n=>n.name).filter(n=>!['csrfmiddlewaretoken','version'].includes(n)).sort());
    assert.deepEqual(fields, ['description','ends_at','image','location','starts_at','title']);
    await page.locator('[data-save-event]').click();
    assert.equal(posts.length,0);
    assert.equal(await page.locator('[data-event-validation]').isVisible(),true);
    await page.locator('#id_title').fill('Synthetic <script>event</script>');
    assert.equal(await page.locator('[data-event-title]').textContent(), 'Synthetic <script>event</script>');
    assert.equal(await page.locator('[data-event-title] script').count(),0);
    await page.locator('#id_title').fill('Synthetic Santolan Community Day');
    await page.locator('#id_description').fill('A synthetic accessible community gathering.');
    await page.locator('#id_location').fill('Synthetic Santolan community hall');
    const calendar = page.locator('[data-event-calendar]');
    await calendar.locator('[data-calendar-year]').selectOption('2027');
    await calendar.locator('[data-calendar-month]').selectOption('1');
    const day = value => calendar.locator(`[data-date="${value}"]`);
    await day('2027-02-01').focus(); await page.keyboard.press('Enter');
    await day('2027-02-10').click();
    await day('2027-02-02').click(); await day('2027-02-07').click();
    await calendar.locator('[data-start-time]').fill('10:30');
    await calendar.locator('[data-end-time]').fill('18:15');
    assert.equal(await page.locator('#id_starts_at').inputValue(),'2027-02-02T10:30');
    assert.equal(await page.locator('#id_ends_at').inputValue(),'2027-02-07T18:15');
    assert.equal(await calendar.locator('.band-end').first().evaluate(n=>getComputedStyle(n).borderTopRightRadius),'999px');
    await day('2027-02-02').focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator(':focus').getAttribute('data-date'),'2027-02-03');
    await calendar.locator('[data-endpoint=end]').click(); await day('2027-02-02').click();
    await calendar.locator('[data-end-time]').fill('09:00');
    await page.locator('[data-save-event]').click();
    assert.equal(posts.length,0);
    assert.match(await page.locator('[data-event-validation]').textContent(),/after the start/);
    await calendar.locator('[data-endpoint=end]').click(); await day('2027-02-07').click();
    await calendar.locator('[data-end-time]').fill('18:15');
    const file = page.locator('#id_image');
    await file.setInputFiles({name:'unsupported.txt', mimeType:'text/plain', buffer:Buffer.from('synthetic')});
    await page.locator('[data-save-event]').click();
    assert.equal(posts.length,0);
    assert.match(await page.locator('[data-image-feedback]').textContent(),/PNG or JPEG/);
    await file.setInputFiles(process.env.QA_IMAGE);
    assert.equal(await page.locator('[data-image-preview]').isVisible(),true);
    await page.locator('[data-remove-image]').click();
    assert.equal(await page.locator('[data-image-preview]').isVisible(),false);
    await file.setInputFiles(process.env.QA_IMAGE);
    assert.equal(await page.locator('[data-event-validation]').isVisible(),false);
    for (const theme of ['dark','light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for (const width of [1600,1440,1280,1024,768,390,320]) {
        await page.setViewportSize({width,height:1000});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,`${theme}/${width}: overflow`);
        assert.deepEqual(await page.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(n=>n.id); return ids.filter((id,i)=>ids.indexOf(id)!==i);}),[]);
        assert.ok((await calendar.boundingBox()).width<=882);
        assert.equal(await page.locator('[data-native-dates]:visible').count(),0);
        const pickerBox = await calendar.locator('.builder-range-picker').boundingBox();
        const datesBox = await calendar.locator('.builder-calendar').boundingBox();
        const timesBox = await calendar.locator('.builder-time-fields').boundingBox();
        const settingsBox = await calendar.locator('.builder-range-settings').boundingBox();
        assert.ok(Math.abs(datesBox.width-pickerBox.width)<1, 'Calendar uses the full available width');
        assert.ok(timesBox.y>=datesBox.y+datesBox.height, 'Time controls follow the calendar');
        if (pickerBox.width>=600) {
          assert.ok(settingsBox.x>=timesBox.x+timesBox.width, 'Compact date controls beside the time controls');
          assert.ok(Math.abs(settingsBox.y-timesBox.y)<1, 'Date and time controls share one row');
        } else {
          assert.ok(settingsBox.y>=timesBox.y+timesBox.height, 'Compact controls stack below times on small screens');
        }
        assert.ok(settingsBox.height<180, 'Date controls stay compact');
        layouts.push({theme,width});
        if ([1600,390].includes(width)) {
          await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
          await page.screenshot({path:path.join(output,`event-create-${theme}-${width}.png`)});
          await calendar.scrollIntoViewIfNeeded();
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          if (width === 390) assert.ok((await page.locator('.builder-steps').boundingBox()).height < 96, 'Compact mobile section navigation');
          await page.screenshot({path:path.join(output,`event-calendar-${theme}-${width}.png`)});
        }
      }
    }
    await page.evaluate(()=>{document.documentElement.dataset.text='largest';document.documentElement.dataset.contrast='true';});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    await page.evaluate(()=>{delete document.documentElement.dataset.text;delete document.documentElement.dataset.contrast;});
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('[data-save-event]').click();
    await page.waitForURL(url=>url.pathname!==route);
    assert.match(new URL(page.url()).pathname,/^\/events\/manage\/[\w-]+\/$/);
    assert.equal(posts.length,1);
    assert.match(await page.locator('body').textContent(),/Draft saved/);
    const detailRoute = new URL(page.url()).pathname;
    allowedPosts.add(detailRoute);
    await page.getByRole('link',{name:'Edit event',exact:true}).click();
    await page.locator('[data-event-builder][data-editing=true]').waitFor();
    allowedPosts.add(new URL(page.url()).pathname);
    const editFields = await page.locator('[data-event-form] [name]').evaluateAll(nodes=>nodes.map(n=>n.name)
      .filter(n=>!['csrfmiddlewaretoken','version','notes','remove_image'].includes(n)).sort());
    assert.deepEqual(editFields,fields);
    assert.equal(await page.locator('[data-current-image] img').evaluate(img=>img.complete && img.naturalWidth>0),true);
    assert.equal(await page.locator('#id_starts_at').inputValue(),'2027-02-02T10:30');
    assert.equal(await page.locator('#id_ends_at').inputValue(),'2027-02-07T18:15');
    await page.locator('#id_location').fill('Synthetic updated community hall');
    for(const theme of ['dark','light']) {
      if(await page.locator('html').getAttribute('data-dashboard-theme')!==theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for(const width of [1440,390]) {
        await page.setViewportSize({width,height:1000});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        await page.screenshot({path:path.join(output,`event-edit-${theme}-${width}.png`),fullPage:true});
      }
    }
    await page.getByRole('button',{name:'Save changes',exact:true}).click();
    await page.waitForURL(base+detailRoute);
    assert.match(await page.locator('main').innerText(),/Synthetic updated community hall/);
    await page.getByRole('button',{name:'Publish event',exact:true}).click();
    await page.getByRole('heading',{name:'Event published',exact:true}).waitFor();
    await page.getByRole('link',{name:'Edit event',exact:true}).click();
    await page.getByText('Saving updates the public event immediately.',{exact:false}).waitFor();
    await page.locator('#id_description').fill('A revised synthetic accessible community gathering.');
    await page.getByRole('button',{name:'Save changes',exact:true}).click();
    await page.waitForURL(base+detailRoute);
    assert.match(await page.locator('main').innerText(),/A revised synthetic accessible community gathering/);
    assert.equal(posts.length,4);
    const nojs = await browser.newContext({javaScriptEnabled:false}); await nojs.addCookies([cookie]);
    const fallback = await nojs.newPage(); await fallback.goto(base+route);
    assert.equal(await fallback.locator('#id_starts_at').isVisible(),true);
    assert.equal(await fallback.locator('#id_ends_at').isVisible(),true);
    assert.equal(await fallback.locator('[data-save-event]').isEnabled(),true);
    await nojs.close();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({layouts,errors,posts:posts.length,
      checks:'Matching create/edit fields; calendar controls; validation; image preview/removal and saved image retention; escaped live summary; responsive themes; no-JS fallback; draft creation/edit/publication and published edit'},null,2));
    console.log(`PASS: ${layouts.length} create layouts and four edit layouts; calendar, image, draft/published edit.`);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
