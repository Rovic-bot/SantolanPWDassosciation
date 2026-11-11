const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT;
  const cookie = {name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: base};
  const errors = [], posts = [], layouts = [], editLayouts = [];
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, reducedMotion: 'reduce', colorScheme: 'dark'});
    await context.addCookies([cookie]);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    let documents = 0;
    page.on('request', request => {
      if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents++;
      if (request.method() === 'POST') {
        assert.match(new URL(request.url()).pathname, /^\/(admin\/programs\/create|programs\/manage\/[\w-]+\/edit\/)$/);
        posts.push(request.url());
      }
    });
    await page.goto(base + '/admin/programs/create');
    await page.waitForFunction(() => document.querySelector('.builder-range-picker')?.hidden === false);
    assert.equal(await page.locator('a[aria-current=page]').textContent(), 'Program Management');
    assert.equal(await page.locator('.builder-header h1').textContent(), 'Create program');
    assert.equal(await page.getByText('Build a program', {exact:false}).count(), 0);
    assert.equal(await page.locator('[data-native-dates]:visible').count(), 0);
    assert.equal(await page.locator('.builder-calendar').count(), 1);
    assert.equal(await page.locator('[data-apply-range], [data-clear-range]').count(), 0);
    assert.equal(await page.locator('#id_resubmission_closes_at').getAttribute('type'), 'hidden');
    await page.locator('[data-review-program]').click();
    assert.equal(await page.locator('[data-validation-summary]').isVisible(), true);
    assert.equal(posts.length, 0);
    await page.locator('#id_name').fill('Synthetic <script>title</script>');
    assert.equal(await page.locator('[data-preview-title]').textContent(), 'Synthetic <script>title</script>');
    assert.equal(await page.locator('[data-preview-title] script').count(), 0);
    await page.locator('#id_name').fill('Synthetic Community Access');
    await page.locator('#id_assistance_type').selectOption('Healthcare & Medical Aid');
    await page.locator('#id_description').fill('Synthetic program for accessible community services.');
    await page.locator('#id_benefit').fill('Synthetic coordinated support for registered members.');
    await page.locator('#id_slots').fill('120');
    await page.locator('#id_ewaf_applicable').uncheck();
    assert.equal(await page.locator('[data-preview-selection]').textContent(), 'Manual review');
    await page.locator('#id_ewaf_applicable').check();
    assert.equal(await page.locator('[data-preview-selection]').textContent(), 'EWAF enabled');
    await page.locator('#id_ewaf_applicable').uncheck();
    assert.equal(await page.locator('[data-preview-capacity]').textContent(), '120 places');
    const calendar = page.locator('[data-shared-calendar]');
    const reg = page.locator('[data-range=registration]'), delivery = page.locator('[data-range=delivery]');
    const month = async (year, value) => {
      await calendar.locator('[data-calendar-year]').selectOption(String(year));
      await calendar.locator('[data-calendar-month]').selectOption(String(value - 1));
    };
    const clickDay = value => calendar.locator(`[data-date="${value}"]`).click();
    const dateValue = name => page.locator(`[name="${name}"]`).inputValue();
    await month(2028, 2);
    assert.equal(await calendar.locator('[data-date="2028-02-29"]').count(), 1);
    // Exact requested behavior: a completed range alternates endpoint changes.
    await month(2026, 11);
    await clickDay('2026-11-01'); await clickDay('2026-11-10');
    assert.equal(await dateValue('registration_opens_at'), '2026-11-01T09:00');
    assert.equal(await dateValue('registration_closes_at'), '2026-11-10T17:00');
    await clickDay('2026-11-02');
    assert.equal(await dateValue('registration_opens_at'), '2026-11-02T09:00');
    assert.equal(await dateValue('registration_closes_at'), '2026-11-10T17:00');
    await clickDay('2026-11-07');
    assert.equal(await dateValue('registration_opens_at'), '2026-11-02T09:00');
    assert.equal(await dateValue('registration_closes_at'), '2026-11-07T17:00');
    await calendar.locator('[data-start-time]').fill('10:30');
    await calendar.locator('[data-end-time]').fill('18:15');
    assert.equal(await dateValue('registration_opens_at'), '2026-11-02T10:30');
    assert.equal(await dateValue('registration_closes_at'), '2026-11-07T18:15');
    await delivery.click(); await month(2026,11);
    await clickDay('2026-11-05'); await clickDay('2026-11-09');
    assert.equal(await dateValue('starts_at'), '2026-11-05T09:00');
    assert.equal(await calendar.getAttribute('data-accent'), 'violet');
    // Both ranges remain visible on overlap; round caps also cover week boundaries.
    assert.equal(await calendar.locator('td:has([data-date="2026-11-06"]) .builder-date-band').count(), 2);
    assert.equal(await calendar.locator('td:has([data-date="2026-11-08"]) [data-band=delivery].band-end').count(), 1);
    assert.equal(await calendar.locator('td:has([data-date="2026-11-09"]) [data-band=delivery].band-start.band-end').count(), 1);
    assert.equal(await calendar.locator('.band-end').first().evaluate(node=>getComputedStyle(node).borderTopRightRadius), '999px');
    for (const theme of ['dark','light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      await calendar.screenshot({path:path.join(output,`shared-calendar-overlap-${theme}.png`)});
    }
    await reg.click();
    assert.equal(await calendar.getAttribute('data-accent'), 'blue');
    assert.equal(await calendar.locator('[data-start-time]').inputValue(), '10:30');
    assert.equal(await calendar.locator('[data-end-time]').inputValue(), '18:15');
    await calendar.locator('[data-start-time]').fill('09:00');
    await calendar.locator('[data-end-time]').fill('17:00');
    await month(2027, 2);
    await clickDay('2027-02-20'); await clickDay('2027-02-17');
    assert.equal(await calendar.locator('.range-start [data-date]').getAttribute('data-date'), '2027-02-17');
    assert.equal(await page.locator('[data-readiness=registration]').getAttribute('data-complete'), 'false');
    await clickDay('2027-02-22');
    assert.equal(await calendar.locator('td.in-range').count(), 6);
    assert.equal(await dateValue('registration_opens_at'), '2027-02-17T09:00');
    assert.equal(await page.locator('[data-readiness=registration]').getAttribute('data-complete'), 'true');
    await delivery.click(); await month(2027, 3);
    await calendar.locator('[data-date="2027-03-01"]').focus();
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Enter');
    assert.equal(await dateValue('starts_at'), '2027-03-02T09:00');
    assert.equal(await dateValue('ends_at'), '2027-03-05T17:00');
    await clickDay('2027-03-07'); await clickDay('2027-03-07');
    await calendar.locator('[data-end-time]').fill('08:00');
    assert.match(await calendar.locator('[data-range-feedback]').textContent(), /after the start/);
    await page.locator('[data-review-program]').click();
    assert.equal(posts.length,0);
    assert.match(await page.locator('[data-validation-summary]').textContent(), /after the start/);
    await calendar.locator('[data-end-time]').fill('17:00');
    assert.equal(await dateValue('ends_at'), '2027-03-07T17:00');
    await calendar.locator('[data-endpoint=start]').click();
    await clickDay('2027-03-02'); await clickDay('2027-03-05');
    assert.equal(await dateValue('starts_at'), '2027-03-02T09:00');
    assert.equal(await dateValue('ends_at'), '2027-03-05T17:00');
    assert.equal(await dateValue('registration_closes_at'), '2027-02-22T17:00');
    await page.locator('[name=eligible_disability_types]').first().check();
    assert.match(await page.locator('[data-readiness=eligibility]').textContent(), /1 selected/);
    for (const [index, kind] of ['text','document','acknowledgement'].entries()) {
      await page.locator('[data-add-question]').click();
      await page.locator(`#id_requirements-${index}-label`).fill(`Synthetic question ${index + 1}`);
      await page.locator(`#id_requirements-${index}-kind`).selectOption(kind);
    }
    await page.locator('[data-remove-question]').nth(1).click();
    assert.equal(await page.locator('#id_requirements-TOTAL_FORMS').inputValue(), '2');
    assert.equal(await page.locator('#id_requirements-1-kind').inputValue(), 'acknowledgement');
    await page.locator('[data-add-question]').click();
    await page.locator('#id_requirements-2-label').fill('Synthetic document');
    await page.locator('#id_requirements-2-kind').selectOption('document');
    assert.equal(await page.locator('[data-ready-count]').textContent(), '6 of 6 setup areas complete');
    assert.equal(await page.locator('[data-validation-summary]').isVisible(), false);
    for (const theme of ['dark', 'light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for (const width of [1600,1440,1280,1024,768,390,320]) {
        await page.setViewportSize({width, height: 1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `${theme}/${width}: page overflow`);
        assert.deepEqual(await page.evaluate(() => { const ids=[...document.querySelectorAll('[id]')].map(node=>node.id); return ids.filter((id,index)=>ids.indexOf(id)!==index); }), []);
        const calendarBox = await calendar.boundingBox();
        assert.ok(calendarBox.width <= 882, `${theme}/${width}: bounded schedule workspace width`);
        const dateGrid = await calendar.locator('.builder-calendar-body').boundingBox();
        const settings = await calendar.locator('.builder-range-settings').boundingBox();
        const sideBySide = await calendar.locator('.builder-range-picker').evaluate(node => node.clientWidth >= 560);
        if (sideBySide) {
          assert.ok(settings.x >= dateGrid.x + dateGrid.width, `${theme}/${width}: date controls on the right`);
          assert.ok(Math.abs(settings.y - dateGrid.y) < 1, `${theme}/${width}: top-aligned calendar and controls`);
          assert.ok(dateGrid.width <= 520, `${theme}/${width}: compact date grid`);
        } else {
          assert.ok(settings.y + settings.height <= dateGrid.y, `${theme}/${width}: stacked controls on smaller screens`);
        }
        assert.equal(await page.locator('.builder-calendar:visible').count(),1);
        const timeGap = await calendar.evaluate(node => node.querySelector('.builder-auto-range').getBoundingClientRect().top - node.querySelector('.builder-time-fields').getBoundingClientRect().bottom);
        assert.ok(timeGap >= 20, `${theme}/${width}: space after time controls`);
        layouts.push({theme,width,calendarWidth:Math.round(calendarBox.width),calendarHeight:Math.round(calendarBox.height),sideBySide});
        if ([1600,390].includes(width)) {
          await page.evaluate(async () => { for(let y=0;y<document.documentElement.scrollHeight;y+=innerHeight) { scrollTo({top:y,behavior:'instant'}); await new Promise(requestAnimationFrame); } scrollTo({top:0,behavior:'instant'}); await new Promise(requestAnimationFrame); });
          await page.screenshot({path:path.join(output,`builder-${theme}-${width}.png`),fullPage:true});
        }
        if (width === 1440) {
          await page.locator('#setup-schedule').evaluate(node => scrollTo({top:node.getBoundingClientRect().top+scrollY-100,behavior:'instant'}));
          await page.screenshot({path:path.join(output,`builder-calendar-${theme}-1440.png`)});
        }
      }
      await page.setViewportSize({width:1600,height:1000});
      await page.locator('#setup-schedule').scrollIntoViewIfNeeded();
      const panel = await page.locator('.builder-summary').boundingBox();
      assert.ok(panel.y >= 76 && panel.y + panel.height <= 1000, `${theme}: sticky summary within viewport`);
      const bar = await page.locator('.builder-action-bar').boundingBox();
      assert.ok(bar.y > 0 && bar.y + bar.height <= 1000, `${theme}: sticky actions`);
      await page.screenshot({path:path.join(output,`builder-calendar-${theme}.png`)});
    }
    await page.setViewportSize({width:390,height:1000});
    await page.evaluate(() => { document.documentElement.dataset.text='largest'; document.documentElement.dataset.contrast='true'; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.emulateMedia({forcedColors:'active'});
    assert.equal(await calendar.locator('.range-start').count(),1);
    await page.emulateMedia({forcedColors:'none'});
    await page.evaluate(() => { delete document.documentElement.dataset.text; delete document.documentElement.dataset.contrast; });
    await page.setViewportSize({width:1600,height:1000});
    const originalDocuments=documents;
    await page.locator('[data-save-draft]').evaluate(button => { button.click(); button.click(); });
    await page.waitForFunction(() => document.querySelector('[data-program-builder]')?.dataset.saved === 'true');
    assert.equal(posts.length,1); assert.equal(documents,originalDocuments);
    assert.match(await page.locator('[data-draft-time]').textContent(), /Last saved/);
    assert.equal(await page.locator('[data-question-rows] [data-question]').count(),0);
    assert.equal(await page.locator('.builder-saved-requirements li').count(),3);
    assert.match(page.url(),/\/programs\/manage\/[\w-]+\/edit\/$/);
    assert.equal(await page.locator('[data-draft-status]').textContent(), 'Draft saved');
    assert.equal(await page.locator('[data-save-draft]').textContent(), 'Update program');
    assert.match(await page.locator('[data-builder-location]').textContent(), /Edit program.*Update program details/);
    assert.match(await page.title(), /Edit program/);
    await page.locator('[data-review-program]').click();
    assert.equal(await page.locator('[data-review-ready]').isVisible(),true);
    assert.equal(posts.length,1);
    await page.locator('#id_name').fill('Synthetic Community Access — updated');
    await page.locator('#id_notes').fill('Synthetic title clarification.');
    await page.locator('[data-review-program]').click();
    await page.waitForFunction(() => document.querySelector('[data-draft-status]').textContent === 'Program updated' && document.querySelector('#id_notes').value === '');
    assert.equal(posts.length,2); assert.equal(documents,originalDocuments);
    assert.equal(await page.locator('[data-review-ready]').isVisible(),true);
    await page.reload();
    assert.equal(await page.locator('#id_name').inputValue(),'Synthetic Community Access — updated');
    assert.equal(await page.locator('[data-draft-status]').textContent(),'Up to date');
    assert.equal(await page.locator('.builder-header h1').textContent(),'Edit program');
    assert.equal(await page.locator('.builder-calendar').count(),1);
    assert.equal(await dateValue('registration_opens_at'), '2027-02-17T09:00');
    assert.equal(await dateValue('ends_at'), '2027-03-05T17:00');
    for (const theme of ['dark', 'light']) {
      if (await page.locator('html').getAttribute('data-dashboard-theme') !== theme) await page.locator('[data-dashboard-theme-toggle]').click();
      for (const width of [1600,768,390]) {
        await page.setViewportSize({width, height:1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1), true);
        assert.equal(await page.locator('[data-save-draft]').textContent(), 'Update program');
        await page.evaluate(() => scrollTo({top:0, behavior:'instant'}));
        editLayouts.push({theme,width});
        await page.screenshot({path:path.join(output,`edit-program-${theme}-${width}.png`)});
      }
    }
    await page.locator('#id_name').fill('Synthetic uncertain save');
    await page.locator('#id_notes').fill('Synthetic simulated connection issue.');
    await page.route('**/programs/manage/**/edit/**', route => route.request().method()==='POST' ? route.abort() : route.continue());
    await page.locator('[data-save-draft]').click();
    await page.waitForFunction(() => document.querySelector('[data-save-draft]').disabled);
    assert.equal(await page.locator('[data-review-program]').isDisabled(),true);

    const nojs = await browser.newContext({javaScriptEnabled:false}); await nojs.addCookies([cookie]);
    const fallback = await nojs.newPage(); await fallback.goto(base+'/admin/programs/create');
    assert.equal(await fallback.locator('[data-native-dates]:visible').count(),2);
    assert.equal(await fallback.locator('[data-save-draft]').isEnabled(),true);
    await nojs.close();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({layouts,editLayouts,errors,confirmedSaves:2,
      checks:'Shared calendar; alternating endpoints (Nov 1-10, Nov 2-10, Nov 2-7), automatic dates/times, independent ranges and overlap, rounded week/end caps, leap date, keyboard navigation, same-day time validation, dynamic questions and removal, XSS-safe preview, native fallback, 14 responsive layouts, themes, sticky summary/actions, high contrast, no document reload on save, duplicate-click protection, persisted draft updates and uncertain-save lockout'},null,2));
    console.log(`PASS: ${layouts.length} responsive layouts; calendars, accessible controls, dynamic questions and two private draft saves.`);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
