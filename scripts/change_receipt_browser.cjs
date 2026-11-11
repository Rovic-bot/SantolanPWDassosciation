/* Read-only display of the synthetic receipt and its locally generated QR. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const directory = process.argv[2];
const html = fs.readFileSync(path.join(directory, 'change-receipt.html'), 'utf8');
assert.ok(html.includes('information-change-notice'));
const qrPath = html.match(/src="([^"]*tracking\/receipt-qr\/[^/]+\/)"/)[1];
const origin = 'http://127.0.0.1:8013';
const receiptPath = '/synthetic-change-receipt/';
const output = path.resolve(__dirname, '../docs/change-receipt-2026-10-29');
fs.mkdirSync(output, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    const errors = [], blocked = [];
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin || request.method() !== 'GET') {
        blocked.push(url.pathname); return route.abort();
      }
      if (url.pathname === receiptPath) return route.fulfill({contentType: 'text/html', body: html});
      if (url.pathname === qrPath) return route.fulfill({contentType: 'image/png',
        body: fs.readFileSync(path.join(directory, 'change-receipt-qr.png'))});
      if (url.pathname.startsWith('/static/')) return route.continue();
      blocked.push(url.pathname); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + receiptPath, {waitUntil: 'networkidle'});
    const notice = page.locator('#information-change-notice');
    assert.equal(await notice.isVisible(), true);
    assert.ok((await notice.innerText()).includes('Please visit the Barangay Santolan office'));
    assert.ok((await page.locator('.event-reference').innerText()).includes('SPWDA-'));
    assert.equal(await page.locator(`img[src="${qrPath}"]`).evaluate(img => img.complete && img.naturalWidth > 0), true);
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({width, height: 1000});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      if (width === 390 || width === 1440) {
        await page.locator('.record-editor').screenshot({path: path.join(output,
          width === 390 ? 'receipt-mobile.png' : 'receipt-desktop.png')});
      }
    }
    await page.emulateMedia({media: 'print'});
    assert.equal(await notice.isVisible(), true);
    assert.deepEqual(errors, []);
    assert.deepEqual(blocked, []);
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({
      synthetic_fixture: true, office_confirmation_notice: true, reference_visible: true,
      qr_loaded: true, notice_printable: true, backend_mutations: 0,
      responsive_widths: [320, 390, 768, 1440], page_errors: errors
    }, null, 2));
    console.log('PASS: receipt notice, reference, QR, print visibility and four responsive widths; no backend mutations.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
