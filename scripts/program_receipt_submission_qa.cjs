/* Real public submission, using only disposable fictional fixtures. */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {QA_URL: origin, QA_OUTPUT: output, QA_VERIFY: verify, QA_APPLY: apply, QA_RECEIPT: receipt} = process.env;
if (!origin || !output || !verify || !apply || !receipt) throw new Error('Synthetic submission required');
(async () => {
  const browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}}), errors = [], posts = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {if (request.method() === 'POST' && new URL(request.url()).pathname === apply) posts.push(request);});
    await page.goto(origin + verify);
    assert.equal(await page.locator('[name="control_number"]').count(), 1, await page.locator('main').innerText());
    await page.locator('[name="control_number"]').fill(process.env.QA_CONTROL);
    await page.locator('[name="full_name"]').fill(process.env.QA_MEMBER);
    await page.getByRole('button', {name:'Verify membership and screen requirements'}).click();
    await page.waitForURL(origin + apply);
    await page.locator('[name="applicant_email"]').fill('receipt-only@example.invalid');
    await page.locator('[name="current_information"]').selectOption('changed');
    await page.locator('[name="change_details"]').fill('PRIVATE-CHANGE-NOTE');
    await page.locator('[name="confirm_information"]').check();
    await page.route(origin + receipt, route => route.abort(), {times:1});
    await page.getByRole('button', {name:'Submit application', exact:true}).click();
    const popup = page.locator('[data-program-receipt-dialog]');
    await popup.getByText(/Your application was submitted, but the receipt could not be loaded/).waitFor();
    assert.equal(page.url(), origin + apply);
    assert.equal(posts.length, 1);
    assert.equal(await page.locator('[data-program-application]').count(), 0);
    await popup.locator('[data-receipt-retry]').click();
    await popup.locator('#program-receipt-reference').waitFor();
    assert.equal(posts.length, 1, 'Receipt retry must never submit the application again');
    assert(await popup.locator('#information-change-notice').isVisible());
    for (const secret of ['PRIVATE-CHANGE-NOTE','receipt-only@example.invalid',process.env.QA_MEMBER,process.env.QA_CONTROL]) {
      assert(!(await popup.innerText()).includes(secret));
    }
    const originalReference = await popup.locator('#program-receipt-reference').textContent();
    const downloaded = page.waitForEvent('download');
    await popup.locator('[data-receipt-image="png"]').click();
    await (await downloaded).saveAs(`${output}/changed-information.png`);
    await popup.screenshot({path:`${output}/submitted-popup-1440.png`});
    await page.keyboard.press('Escape');
    await popup.waitFor({state:'hidden'});
    assert(await page.getByRole('button', {name:'View receipt', exact:true}).isVisible());
    await page.getByRole('button', {name:'View receipt', exact:true}).click();
    await popup.locator('#program-receipt-reference').waitFor();
    assert.equal(await popup.locator('#program-receipt-reference').textContent(), originalReference);
    assert.equal(posts.length, 1);
    await page.setViewportSize({width:390,height:844});
    assert(await popup.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
    await popup.screenshot({path:`${output}/submitted-popup-390.png`});
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${output}/results.json`, JSON.stringify({samePage:true,receiptLoadRecovery:true,
      oneSubmission:posts.length,receiptReopened:true,officeNotice:true,privateFieldsOmitted:true,png:true,mobile:true,errors},null,2));
    console.log(`Submission popup and image export passed. Artifacts: ${output}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode = 1;});
