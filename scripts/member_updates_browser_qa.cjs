const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT, identity = JSON.parse(process.env.QA_IDENTITY), errors = [], checks = [];
  const programIdentity = JSON.parse(process.env.QA_PROGRAM_IDENTITY);
  const publicContext = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
  const page = await publicContext.newPage(); page.on('pageerror', e => errors.push(e.message));
  const adminContext = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
  await adminContext.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: base}]);
  const admin = await adminContext.newPage(); admin.on('pageerror', e => errors.push(e.message));
  async function verifyMember(target, keyboard=false, awaiting=false) {
    await target.bringToFront();
    await target.goto(base + '/members/update/');
    const inputs = await target.locator('form.record-editor input:not([type=hidden])').evaluateAll(nodes => nodes.map(node => node.name));
    assert.deepEqual(inputs, ['control_number', 'full_name']);
    for (const [name, value] of Object.entries(identity)) await target.locator(`[name="${name}"]`).fill(value);
    const send = target.getByRole('button', {name: 'Send verification code', exact: true});
    if (keyboard) {await send.focus(); await target.keyboard.press('Enter');} else await send.click();
    await target.locator('[name=code]').fill('123456');
    const verify = target.getByRole('button', {name: 'Verify and open my information', exact: true});
    if (keyboard) {await verify.focus(); await target.keyboard.press('Enter');} else await verify.click();
    if (awaiting) await target.getByRole('heading',{name:'Your update is awaiting review',exact:true}).waitFor();
    else await target.locator('[name=pwd_number]').waitFor();
  }
  async function layout(target, name, adminPage=false) {
    for (const mode of ['light', 'dark', 'high-contrast']) for (const width of [1440,390,320]) {
      await target.setViewportSize({width, height: 1000});
      await target.evaluate(({mode,adminPage}) => {
        localStorage.setItem('santolan-display', JSON.stringify({dark: mode !== 'light', contrast: mode === 'high-contrast', motion: true}));
        if (adminPage) localStorage.setItem('santolan-dashboard-theme', mode === 'light' ? 'light' : 'dark');
      }, {mode,adminPage});
      await target.reload();
      if (name === 'update-confirmation') {
        await target.waitForFunction(() => document.querySelector('[data-member-update-confirmation-dialog]')?.matches(':modal'));
        const box = await target.locator('[data-member-update-confirmation-dialog]').boundingBox();
        assert(box.x >= 0 && box.y >= 0 && box.x + box.width <= width + 1 && box.y + box.height <= 1001, 'Popup fits the viewport');
        assert.equal(await target.locator('.resident-form-layout').count(), 0);
      }
      assert(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name} ${mode} ${width} overflow`);
      const duplicate = await target.evaluate(() => [...document.querySelectorAll('[id]')].map(n => n.id).filter((id,i,ids) => ids.indexOf(id) !== i));
      assert.deepEqual(duplicate, [], `${name}: duplicate ids`);
      if (width !== 320) await target.screenshot({path: path.join(output, `${name}-${mode}-${width}.png`)});
      checks.push({name,mode,width,overflow:false});
    }
    await target.setViewportSize({width:1440,height:1000});
  }
  async function attemptProgram() {
    const applicant = await publicContext.newPage();
    await applicant.goto(base + process.env.QA_PROGRAM_VERIFY);
    const form = applicant.locator('form').filter({has: applicant.locator('[name=control_number]')});
    for (const [name, value] of Object.entries(programIdentity)) await form.locator(`[name="${name}"]`).fill(value);
    await form.locator('button[type=submit]').click();
    return applicant;
  }
  try {
    await page.goto(base + '/');
    const positions = await page.locator('#ewaf, #member-update').evaluateAll(nodes => nodes.map(n => {const b=n.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width};}));
    assert.equal(positions.length,2); assert(Math.abs(positions[0].y-positions[1].y)<2); assert(positions[1].x>positions[0].x);
    assert.equal(await page.locator('#home-guidance article').count(),6);
    await page.locator('#home-guidance').screenshot({path:path.join(output,'home-six-cards.png')});
    await page.getByRole('link',{name:'Update my information',exact:false}).click();
    assert.equal(new URL(page.url()).pathname,'/members/update/');
    await verifyMember(page);
    assert.equal(await page.locator('[name=guardian_name]').inputValue(),'Original guardian');
    assert(await page.locator('[name=pwd_number]').isDisabled());
    await layout(page,'prefilled-form');
    await page.locator('[name=guardian_name]').fill('Updated synthetic guardian');
    await page.locator('[name=email]').fill('updated@example.invalid');
    await page.locator('[name=acknowledgement]').check();
    await page.getByRole('button',{name:'Submit updated information',exact:true}).click();
    await page.getByRole('heading',{name:'Your update is awaiting review',exact:true}).waitFor();
    await layout(page,'update-confirmation');
    const finishButton = page.getByRole('button',{name:'Finish and return home',exact:true});
    const closeButton = page.getByRole('button',{name:'Close and return home',exact:true});
    await finishButton.focus(); await page.keyboard.press('Tab');
    assert(await closeButton.evaluate(node=>node===document.activeElement));
    await page.keyboard.press('Shift+Tab');
    assert(await finishButton.evaluate(node=>node===document.activeElement));
    const closeContext = await browser.newContext({viewport:{width:390,height:800},reducedMotion:'reduce'});
    const closePage = await closeContext.newPage(); await verifyMember(closePage,false,true);
    await closePage.getByRole('button',{name:'Close and return home',exact:true}).click();
    await closePage.waitForURL(base+'/');
    await closePage.goto(base+'/members/update/information/');
    assert.equal(new URL(closePage.url()).pathname,'/members/update/');
    await closeContext.close();
    const fallbackContext = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000},reducedMotion:'reduce'});
    const fallback = await fallbackContext.newPage(); await verifyMember(fallback,true,true);
    assert(await fallback.locator('[data-member-update-confirmation]').isVisible());
    assert.equal(await fallback.locator('dialog[open]').count(),0);
    await fallback.getByRole('button',{name:'Finish and return home',exact:true}).focus();
    await fallback.keyboard.press('Enter'); await fallback.waitForURL(base+'/');
    await fallbackContext.close();
    await admin.goto(base + process.env.QA_DIRECTORY + '?status=update_needed');
    assert.equal(await admin.locator('.directory-row [data-status=update_needed]').count(),1);
    await admin.locator('[data-preview-update]').click();
    assert.equal(await admin.locator('.member-update-comparison > div').count(),2);
    assert.match(await admin.locator('.member-update-comparison').innerText(),/Original guardian/);
    await layout(admin,'admin-comparison',true);
    await admin.getByRole('button',{name:'Verify this information',exact:true}).click();
    await admin.getByRole('button',{name:'Approve updated information',exact:true}).waitFor();
    await admin.locator('[name=reason]').fill('Synthetic screening requires further verification.');
    await admin.getByRole('button',{name:'Mark needs verification',exact:true}).click();
    await admin.waitForFunction(() => document.querySelector('.member-update-state')?.textContent==='Needs verification');
    const blocked = await attemptProgram();
    assert.match(await blocked.locator('main').innerText(),/needs verification/i);
    await blocked.close();
    await admin.locator('[name=reason]').fill('Synthetic office interview completed; updated information verified.');
    await admin.locator('[name=interview_confirmed]').check();
    await admin.getByRole('button',{name:'Approve updated information',exact:true}).click();
    await admin.waitForFunction(() => document.querySelector('.member-update-state')?.textContent==='Approved');
    const allowed = await attemptProgram();
    await allowed.waitForURL('**/apply/'); await allowed.close();
    await page.bringToFront(); await page.keyboard.press('Escape');
    await page.waitForURL(base+'/');
    await page.goto(base+'/members/update/information/');
    assert.equal(new URL(page.url()).pathname,'/members/update/');
    const nojsContext = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000},reducedMotion:'reduce'});
    const nojs = await nojsContext.newPage(); await verifyMember(nojs,true);
    assert.equal(await nojs.locator('[name=guardian_name]').inputValue(),'Updated synthetic guardian');
    assert(await nojs.locator('[name=pwd_number]').isDisabled());
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({homeSideBySide:true,identityCode:true,pwdLocked:true,checks,confirmationPopup:true,popupKeyboardFocus:true,closeAndEscapeClearAccess:true,noJavaScriptConfirmation:true,comparisonOnlyChanges:true,officeEmail:true,needsVerificationBlocks:true,approvalRestores:true,finishClearsAccess:true,noJavaScript:true,errors},null,2));
    console.log('Passed member update from home card to verified prefill, staff comparison, office invitation, application block, reapproval and no-JavaScript access.');
  } catch(error) {await page.screenshot({path:path.join(output,'public-failure.png')});await admin.screenshot({path:path.join(output,'admin-failure.png')});throw error;}
  finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
