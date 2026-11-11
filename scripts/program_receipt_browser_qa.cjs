/* Launched only by the disposable Django test, with a fictional receipt session. */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {QA_URL: origin, QA_ROUTE: route, QA_SESSION: session, QA_REFERENCE: reference, QA_OUTPUT: output} = process.env;
if (!origin || !route || !session || !reference || !output) throw new Error('Disposable receipt fixture required');

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:960}});
    await context.addCookies([{name:'sessionid',value:session,url:origin}]);
    await context.grantPermissions(['clipboard-read','clipboard-write'], {origin});
    const page = await context.newPage(), errors = [], widths = [];
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(origin + route);
    assert.equal(response.status(), 200);
    assert.match(response.headers()['cache-control'], /no-store/);
    await page.locator('[data-receipt-copy]:not([hidden])').waitFor();
    const popup = page.locator('[data-program-receipt-dialog]');
    assert(await popup.evaluate(el => el.open));
    assert(await popup.evaluate(el => el.contains(document.activeElement)));
    await page.waitForFunction(() => document.querySelector('.program-receipt-qr img')?.naturalWidth > 0);
    assert.equal(await page.locator('main').evaluate(el => getComputedStyle(el).backgroundColor), 'rgba(0, 0, 0, 0)');
    assert.equal(await page.locator('#program-receipt-reference').textContent(), reference);
    for (const secret of ['PRIVATE-SUBMITTED-ANSWER','PRIVATE-ASSESSMENT',process.env.QA_MEMBER,process.env.QA_CONTROL]) {
      assert(!(await page.locator('main').textContent()).includes(secret));
    }
    for (const width of [1440,1024,768,390,320]) {
      await page.setViewportSize({width,height:960});
      const geometry = await page.evaluate(() => {
        const main = document.querySelector('.program-receipt-main').getBoundingClientRect();
        const tracking = document.querySelector('.program-receipt-tracking').getBoundingClientRect();
        return {overflow:document.documentElement.scrollWidth > innerWidth + 1,
          columns:tracking.left > main.right, stacked:tracking.top >= main.bottom};
      });
      assert.equal(geometry.overflow, false, `Overflow at ${width}px`);
      assert(await popup.evaluate(el => el.scrollWidth <= el.clientWidth + 1), `Popup overflow at ${width}px`);
      assert(width > 850 ? geometry.columns : geometry.stacked, `Receipt layout at ${width}px`);
      widths.push({width,...geometry});
      if ([1440,390].includes(width)) await page.screenshot({path:`${output}/receipt-${width}.png`,fullPage:true});
    }
    await page.setViewportSize({width:1440,height:960});
    // Receipt dialogs share the public palette in both normal and hover states.
    await page.evaluate(() => { document.documentElement.dataset.publicTheme = 'dark'; });
    assert.equal(await page.locator('.program-receipt-card').first().evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(36, 34, 32)');
    await page.locator('.program-receipt-track-button').hover();
    assert.equal(await page.locator('.program-receipt-track-button').evaluate(el => getComputedStyle(el).color), 'rgb(28, 26, 24)');
    await page.screenshot({path:`${output}/receipt-dark.png`,fullPage:true});
    await page.evaluate(() => { document.documentElement.dataset.publicTheme = 'light'; });
    for (const format of ['png','jpeg']) {
      const promised = page.waitForEvent('download');
      await page.locator(`[data-receipt-image="${format}"]`).click();
      const download = await promised;
      assert.equal(download.suggestedFilename(), `program-receipt-${reference}.${format}`);
      await download.saveAs(`${output}/receipt.${format}`);
      const bytes = fs.readFileSync(`${output}/receipt.${format}`);
      assert.equal(bytes.subarray(0, format === 'png' ? 8 : 3).toString('hex'), format === 'png' ? '89504e470d0a1a0a' : 'ffd8ff');
    }
    await page.evaluate(() => {
      const qr = document.querySelector('.program-receipt-qr img');
      qr.decode = async () => {throw new Error('QR image failed');};
    });
    await page.locator('[data-receipt-image="png"]').click();
    await page.getByText(/The image could not be saved/).waitFor();
    assert(await page.locator('[data-receipt-image="png"]').isEnabled());
    await page.evaluate(() => {delete document.querySelector('.program-receipt-qr img').decode;});
    const copy = page.locator('[data-receipt-copy]');
    await copy.focus();
    await page.keyboard.press('Enter');
    await page.getByText('Reference copied.',{exact:true}).waitFor();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), reference);
    await page.evaluate(() => Object.defineProperty(navigator,'clipboard',{
      configurable:true,value:{writeText:async () => {throw new Error('Clipboard denied');}}}));
    await copy.click();
    await page.getByText("Reference selected. Use your device's copy command.",{exact:true}).waitFor();
    assert.equal(await page.evaluate(() => getSelection().toString()), reference);
    await page.evaluate(() => {window.print = () => {window.receiptPrintRequested = true;};});
    await page.locator('[data-receipt-print]').click();
    assert(await page.evaluate(() => window.receiptPrintRequested));
    const receiptURL = page.url();
    await page.locator('.program-receipt [data-tracking-open]').click();
    const dialog = page.locator('[data-tracking-dialog]');
    await dialog.locator('#id_reference').waitFor();
    assert.equal(await dialog.locator('#id_reference').inputValue(), reference);
    assert.equal(page.url(), receiptURL);
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(), false);
    await page.emulateMedia({media:'print'});
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    assert(await page.locator('#program-receipt-reference').isVisible());
    assert(await page.locator('.program-receipt-qr img').isVisible());
    assert.equal(await page.locator('[data-receipt-copy]').isVisible(), false);
    assert.equal(await page.locator('.portal-navigation').isVisible(), false);
    assert(await page.getByText(/Submission does not guarantee eligibility or selection/).isVisible());
    await page.screenshot({path:`${output}/receipt-print.png`,fullPage:true});
    await page.pdf({path:`${output}/receipt-print.pdf`,format:'A4',printBackground:true,
      margin:{top:'12mm',bottom:'12mm',left:'12mm',right:'12mm'}});
    await page.emulateMedia({media:'screen'});
    await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
    assert.equal(await page.locator('.program-receipt-guidance').evaluate(el => el.open), false);
    await page.evaluate(() => document.documentElement.setAttribute('data-contrast','true'));
    await page.screenshot({path:`${output}/receipt-contrast.png`,fullPage:true});
    await page.keyboard.press('Escape');
    await popup.waitFor({state:'hidden'});
    assert.equal(await popup.locator('[data-program-receipt]').count(), 0);
    assert(await page.locator('[data-receipt-reopen]').evaluate(el => el === document.activeElement));
    await page.locator('[data-receipt-reopen]').click();
    await popup.locator('#program-receipt-reference').waitFor();
    assert.equal(await popup.locator('#program-receipt-reference').textContent(), reference);
    await popup.locator('[data-receipt-close]').focus();
    await page.keyboard.press('Shift+Tab');
    assert(await popup.evaluate(el => el.contains(document.activeElement)));
    assert(await popup.locator('.program-receipt-guidance summary').evaluate(el => el === document.activeElement));
    await page.keyboard.press('Enter');
    assert(await popup.locator('.program-receipt-guidance').evaluate(el => el.open));
    const plain = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    await plain.addCookies([{name:'sessionid',value:session,url:origin}]);
    const fallback = await plain.newPage();
    await fallback.goto(receiptURL);
    assert(await fallback.locator('#program-receipt-reference').isVisible());
    assert.equal(await fallback.locator('[data-receipt-copy]').isVisible(), false);
    assert.equal(await fallback.locator('[data-receipt-print]').isVisible(), false);
    await fallback.locator('.program-receipt-guidance summary').click();
    assert(await fallback.getByText(/save or print this confirmation using your browser/).isVisible());
    await fallback.locator('.program-receipt [data-tracking-open]').click();
    assert(await fallback.locator('#id_reference').isVisible());
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${output}/results.json`, JSON.stringify({widths,errors,copy:true,
      copyFallback:true,keyboard:true,trackingPopup:true,privateQR:true,print:true,
      receiptPopup:true,reopen:true,png:true,jpeg:true,exportFailureRecovery:true,
      noJavaScriptFallback:true,recordsUnchanged:true},null,2));
    console.log(`Receipt layout, copy, tracking, print and fallback checks passed. Artifacts: ${output}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode = 1;});
