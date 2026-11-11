const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1280, height: 900}, reducedMotion: 'reduce'});
    const base = process.env.QA_URL;
    await context.addCookies([{name: 'sessionid', value: process.env.QA_SESSION, url: base}]);
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
      ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + process.env.QA_PREVIEW);
    const dialog = page.locator('#program-results-dialog');
    await dialog.waitFor({state: 'visible'});
    await dialog.getByRole('button', {name: 'Publish results', exact: true}).click();
    await page.waitForFunction(() => !document.querySelector('#program-results-dialog').hasAttribute('aria-busy'));
    await dialog.getByText('0 of 1 accepted by the email service.', {exact: false}).waitFor();
    assert.match(await dialog.innerText(), /Resend needs an API key and a verified sending domain/);
    await dialog.getByText('View certificate delivery details', {exact: true}).click();
    await dialog.getByText('fictional-member@example.invalid', {exact: false}).waitFor();
    const download = dialog.getByRole('link', {name: 'Download certificate'});
    const response = await context.request.get(await download.getAttribute('href'));
    assert.equal(response.status(), 200);
    assert.match(response.headers()['content-type'], /application\/pdf/);
    assert.match(response.headers()['content-disposition'], /Certificate\.pdf/);
    assert.equal((await response.body()).subarray(0, 5).toString(), '%PDF-');
    await dialog.locator('.results-certificate-status').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'certificate-status-desktop.png')});
    await dialog.getByRole('button', {name: 'Refresh delivery status'}).click();
    await page.waitForFunction(() => !document.querySelector('#program-results-dialog').hasAttribute('aria-busy'));
    await dialog.getByText('0 of 1 accepted by the email service.', {exact: false}).waitFor();
    await dialog.getByRole('button', {name: 'Publish results', exact: true}).click();
    await page.waitForFunction(() => !document.querySelector('#program-results-dialog').hasAttribute('aria-busy'));
    await dialog.getByText('0 of 1 accepted by the email service.', {exact: false}).waitFor();
    await page.setViewportSize({width: 390, height: 844});
    assert.ok((await dialog.boundingBox()).width < 390);
    await dialog.locator('.results-certificate-status').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'certificate-status-mobile.png')});
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(), false);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({publication: 'passed', pendingSetup: 'passed',
      privateDownload: 'passed', repeatPublication: 'passed', mobile: 'passed', browserErrors: errors}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
