/* Fictional documents only; refuses all application submissions. */
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const http = require('node:http');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = process.cwd();
const output = process.env.OCR_ARTIFACT_DIR || path.join(root, '.local/ocr-browser');
fs.mkdirSync(output, {recursive: true});
const fixtures = process.env.OCR_FIXTURES;
let server;
async function imageFor(page, lines) {
  const data = await page.evaluate(lines => {
    const canvas = document.createElement('canvas'); canvas.width = 1600; canvas.height = 1100;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 1600, 1100);
    ctx.fillStyle = '#111'; ctx.font = '32px Arial';
    lines.forEach((line, index) => ctx.fillText(line, 65, 75 + index * 68));
    return canvas.toDataURL('image/png').split(',')[1];
  }, lines);
  return {name: 'fictional-id.png', mimeType: 'image/png', buffer: Buffer.from(data, 'base64')};
}
(async () => {
  let base = process.env.OCR_URL;
  if (!base) {
    assert(fixtures, 'Set OCR_FIXTURES or OCR_URL');
    server = http.createServer((req, res) => {
      if (req.method !== 'GET') {res.writeHead(405); res.end(); return;}
      const url = new URL(req.url, 'http://localhost');
      const file = url.pathname.startsWith('/static/') ? path.join(root, url.pathname) : path.join(fixtures, url.pathname);
      if (!file.startsWith(root + path.sep) && !file.startsWith(path.resolve(fixtures) + path.sep)) {res.writeHead(403); res.end(); return;}
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {res.writeHead(404); res.end(); return;}
      const mime = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.png': 'image/png', '.svg': 'image/svg+xml', '.gz': 'application/gzip', '.wasm': 'application/wasm'}[path.extname(file)] || 'application/octet-stream';
      res.writeHead(200, {'Content-Type': mime}); fs.createReadStream(file).pipe(res);
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    base = `http://127.0.0.1:${server.address().port}`;
  }
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']});
  const results = [], errors = [], requests = [], blocked = [];
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, permissions: ['camera']});
    await context.route('**/*', route => {
      const request = route.request(); requests.push({url: request.url(), method: request.method()});
      if (request.method() !== 'GET' || (!request.url().startsWith(base) && !request.url().startsWith('data:'))) {
        blocked.push({url: request.url(), method: request.method()}); return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
    const routes = process.env.OCR_URL ? ['/membership/registration/apply/', '/membership/registration/pdao/apply/'] :
      ['/association.html', '/pdao.html', '/onsite-association.html', '/onsite-pdao.html'];
    const lines = ['FICTIONAL TEST CARD - NOT VALID IDENTIFICATION', 'Last Name: DELA CRUZ',
      'First Name: JUAN MIGUEL', 'Middle Name: SANTOS', 'Date of Birth: 21 January 1990',
      'PWD ID No: 00-1234-001-0000042', 'Address: 123 Mabini Street, Barangay Santolan, Pasig City',
      'Sex: Male', 'Mobile Number: 09171234567', 'Email: applicant@example.test'];
    for (const [index, route] of routes.entries()) {
      await page.goto(base + route); await page.locator('[data-document-ocr]:visible').waitFor();
      // Avoid the existing first-interaction privacy popup: set the preexisting
      // value through the form DOM and keep this test focused on OCR.
      await page.locator('[name=last_name]').evaluate(input => {input.value = 'KEEP MY ENTRY';});
      const before = await page.locator('form.registration-editor').evaluate(form => [...new FormData(form).keys()]);
      await page.locator('[data-ocr-file]').setInputFiles(await imageFor(page, lines));
      await page.locator('[data-ocr-read]').click();
      await page.locator('[data-ocr-results]:visible').waitFor({timeout: 100000});
      assert.match(await page.locator('[data-ocr-text]').textContent(), /DELA CRUZ/);
      assert.equal(await page.locator('[name=first_name]').inputValue(), '');
      await page.locator('[name=city]').evaluate(input => {input.value = 'MY CORRECTION';});
      await page.locator('[data-ocr-apply]').click();
      assert.equal(await page.locator('[name=first_name]').inputValue(), 'JUAN MIGUEL');
      assert.equal(await page.locator('[name=last_name]').inputValue(), 'KEEP MY ENTRY');
      assert.equal(await page.locator('[name=birthdate]').inputValue(), '1990-01-21');
      assert.equal(await page.locator('[name=pwd_number]').inputValue(), '00-1234-001-0000042');
      assert.equal(await page.locator('[name=house_street]').inputValue(), '123 Mabini Street');
      assert.equal(await page.locator('[name=city]').inputValue(), 'MY CORRECTION');
      assert.equal(await page.locator('[name=acknowledgement]').isChecked(), false);
      assert.deepEqual(await page.locator('form.registration-editor').evaluate(form => [...new FormData(form).keys()]), before);
      const field = page.locator('[data-ocr-fields] .document-ocr-field').filter({has: page.locator('input[aria-label^="Review Last name"]')});
      await field.locator('input[type=checkbox]').check(); await page.locator('[data-ocr-apply]').click();
      assert.equal(await page.locator('[name=last_name]').inputValue(), 'DELA CRUZ');
      await page.locator('[data-ocr-undo]').click(); assert.equal(await page.locator('[name=last_name]').inputValue(), 'KEEP MY ENTRY');
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `overflow ${route} ${width}`);
        if (index < 2 && width !== 320) await page.locator('[data-document-ocr]').screenshot({path: path.join(output, `scan-${index}-${width}.png`)});
      }
      if (index < 2) {
        await page.evaluate(() => {document.documentElement.dataset.publicTheme = 'dark'; document.documentElement.dataset.dashboardTheme = 'dark';});
        await page.locator('[data-document-ocr]').screenshot({path: path.join(output, `scan-${index}-dark-320.png`)});
      }
      await page.locator('[data-ocr-clear]').click();
      assert.equal(await page.locator('[data-ocr-text]').textContent(), '');
      assert.equal(await page.locator('[name=first_name]').inputValue(), 'JUAN MIGUEL');
      results.push({route, actualOCR: true, reviewedAutofill: true, existingValues: true, noSubmissionFields: true, mobileReflow: true});
    }
    // Receipt mode must not confuse merchant details with applicant details.
    await page.goto(base + routes[0]); await page.locator('[data-ocr-kind]').selectOption('receipt');
    await page.locator('[data-ocr-file]').setInputFiles(await imageFor(page, ['FICTIONAL TEST RECEIPT',
      'Name: EXAMPLE STORE', 'Email: merchant@example.test', 'Receipt No: 999999',
      'Customer: CRUZ, ANA', 'Customer Mobile: 09171234567', 'Total: 500']));
    await page.locator('[data-ocr-read]').click(); await page.locator('[data-ocr-results]:visible').waitFor({timeout: 100000});
    await page.locator('[data-ocr-apply]').click();
    assert.equal(await page.locator('[name=first_name]').inputValue(), 'ANA');
    assert.equal(await page.locator('[name=pwd_number]').inputValue(), '');
    assert.equal(await page.locator('[name=email]').inputValue(), '');
    results.push({receiptCustomerOnly: true});
    await page.locator('[data-ocr-clear]').click();
    await page.locator('[data-ocr-camera]').click();
    await page.waitForFunction(() => document.querySelector('[data-ocr-video]').videoWidth > 0);
    await page.evaluate(() => {window.testCameraTracks = document.querySelector('[data-ocr-video]').srcObject.getTracks();});
    await page.locator('[data-ocr-capture]').click();
    assert(await page.evaluate(() => window.testCameraTracks.every(track => track.readyState === 'ended')));
    assert(await page.locator('[data-ocr-preview]').isVisible());
    results.push({syntheticCameraCaptureAndRelease: true});
    await page.locator('[data-ocr-clear]').click();
    await page.locator('[data-ocr-file]').setInputFiles({name: 'bad.png', mimeType: 'image/png', buffer: Buffer.from('invalid')});
    await page.waitForFunction(() => document.querySelector('[data-ocr-status]').textContent.includes('could not be read'));
    assert.equal(await page.locator('[data-ocr-preview]').isVisible(), false);
    results.push({corruptImageFallback: true});
    await page.evaluate(() => {navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Test denial', 'NotAllowedError'));});
    await page.locator('[data-ocr-camera]').click();
    await page.waitForFunction(() => document.querySelector('[data-ocr-status]').textContent.includes('permission denied'));
    assert(await page.locator('[data-ocr-phone]').isVisible());
    results.push({cameraDeniedManualFallback: true});
    // Track native workers to verify cancellation during initialization really
    // releases the engine, including a failed language download.
    await page.evaluate(() => {
      const NativeWorker = window.Worker; window.testActiveWorkers = 0;
      window.Worker = class extends NativeWorker {
        constructor(...args) {super(...args); window.testActiveWorkers++;}
        terminate() {if (!this.testEnded) {window.testActiveWorkers--; this.testEnded = true;} super.terminate();}
      };
    });
    await page.locator('[data-ocr-file]').setInputFiles(await imageFor(page, lines));
    await page.locator('[data-ocr-read]').click(); await page.locator('[data-ocr-cancel]').click();
    assert.equal(await page.evaluate(() => window.testActiveWorkers), 0);
    assert.equal(await page.locator('[data-ocr-results]').isVisible(), false);
    results.push({cancelReleasesWorker: true});
    const failLanguage = route => route.abort();
    await page.route('**/eng.traineddata.gz', failLanguage);
    await page.locator('[data-ocr-read]').click();
    await page.waitForFunction(() => document.querySelector('[data-ocr-status]').textContent.includes('could not finish'), {timeout: 20000});
    assert.equal(await page.evaluate(() => window.testActiveWorkers), 0);
    await page.unroute('**/eng.traineddata.gz', failLanguage);
    results.push({failedDownloadReleasesWorker: true});
    const noJS = await browser.newContext({javaScriptEnabled: false}); const fallback = await noJS.newPage();
    await fallback.goto(base + routes[0]); assert(await fallback.locator('[name=first_name]').isVisible());
    assert.equal(await fallback.locator('[data-document-ocr]').isVisible(), false); await noJS.close();
    results.push({manualFormWithoutJavaScript: true});
    assert.equal(blocked.filter(item => item.method !== 'GET').length, 0, 'unexpected submission');
    assert.equal(requests.filter(item => item.url.includes('jsdelivr') || item.url.includes('projectnaptha')).length, 0, 'external OCR dependency');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({results, errors, blocked, requests}, null, 2));
    console.log(JSON.stringify({passed: results.length, routes, errors, output}));
  } finally {await browser.close(); if (server) await new Promise(resolve => server.close(resolve));}
})().catch(error => {console.error(error); process.exitCode = 1; if (server) server.close();});
