/* Mobile capture routing and scanner layout; fictional images, no submissions. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium, devices} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = process.cwd();
const fixtures = path.resolve(process.env.OCR_FIXTURES || '.local/pdao-documents-20261128/fixtures');
const output = path.resolve(process.env.OCR_ARTIFACT_DIR || '.local/pdao-documents-20261128/capture');
fs.mkdirSync(output, {recursive: true});
const server = http.createServer((req, res) => {
  if (req.method !== 'GET') {res.writeHead(405); res.end(); return;}
  const url = new URL(req.url, 'http://localhost');
  const file = url.pathname.startsWith('/static/') ? path.join(root, url.pathname) : path.join(fixtures, url.pathname);
  if ((!file.startsWith(root + path.sep) && !file.startsWith(fixtures + path.sep)) || !fs.existsSync(file)) {res.writeHead(404); res.end(); return;}
  const mime = {'.js':'text/javascript', '.css':'text/css', '.html':'text/html', '.png':'image/png', '.svg':'image/svg+xml', '.webp':'image/webp'}[path.extname(file)];
  res.writeHead(200, {'Content-Type': mime || 'application/octet-stream'}); fs.createReadStream(file).pipe(res);
});
async function picture(page, color) {
  const data = await page.evaluate(color => {
    const canvas = document.createElement('canvas'); canvas.width = 500; canvas.height = 300;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = color; ctx.fillRect(0, 0, 500, 300);
    ctx.fillStyle = '#111'; ctx.font = '28px Arial'; ctx.fillText('FICTIONAL TEST IMAGE', 30, 90);
    return canvas.toDataURL('image/png').split(',')[1];
  }, color);
  return {name:'fictional.png', mimeType:'image/png', buffer:Buffer.from(data, 'base64')};
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], results = [];
  try {
    for (const device of ['Pixel 7', 'iPhone 13', 'iPad Pro 11']) {
      const context = await browser.newContext({...devices[device], defaultBrowserType:undefined});
      await context.route('**/*', route => route.request().method() === 'GET' && route.request().url().startsWith(base) ? route.continue() : route.abort());
      await context.addInitScript(() => {
        window.embeddedCameraRequests = 0;
        navigator.mediaDevices.getUserMedia = () => {window.embeddedCameraRequests++; return Promise.reject(new Error('Mobile must use native camera'));};
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      for (const route of ['association', 'pdao', 'onsite-association', 'onsite-pdao']) {
        await page.goto(base + '/' + route + '.html');
        await page.locator('[data-document-ocr]:visible').waitFor();
        for (const side of ['front', 'back']) {
          const choosing = page.waitForEvent('filechooser');
          await page.locator(`[data-ocr-camera="${side}"]`).click();
          const chooser = await choosing;
          assert.equal(await chooser.element().getAttribute('capture'), 'environment');
          assert.equal(await chooser.element().getAttribute('data-ocr-photo'), '');
          await chooser.setFiles(await picture(page, side === 'front' ? '#ddd' : '#cfc'));
          await page.locator(`[data-ocr-thumbnail="${side}"]:visible`).waitFor();
          assert.equal(await page.locator('[data-ocr-camera-panel]').isVisible(), false);
        }
        assert.equal(await page.locator('[data-ocr-count]').textContent(), '2 of 2 sides attached');
        const front = await page.locator('[data-ocr-thumbnail=front]').getAttribute('src');
        const cancel = page.waitForEvent('filechooser');
        await page.locator('[data-ocr-camera=front]').click();
        await (await cancel).setFiles([]);
        assert.equal(await page.locator('[data-ocr-thumbnail=front]').getAttribute('src'), front);
        const gallery = page.waitForEvent('filechooser');
        await page.locator('[data-ocr-upload=back]').click();
        const galleryChooser = await gallery;
        assert.equal(await galleryChooser.element().getAttribute('capture'), null);
        await galleryChooser.setFiles(await picture(page, '#ddf'));
        assert.equal(await page.locator('[data-ocr-thumbnail=front]').getAttribute('src'), front);
        await page.locator('[data-ocr-kind]').selectOption('receipt');
        assert.equal(await page.locator('[data-ocr-card=back]').isVisible(), false);
        const receipt = page.waitForEvent('filechooser');
        await page.locator('[data-ocr-camera=front]').click();
        const receiptChooser = await receipt;
        assert.equal(await receiptChooser.element().getAttribute('capture'), 'environment');
        await receiptChooser.setFiles(await picture(page, '#ffd'));
        await page.locator('[data-ocr-thumbnail=front]:visible').waitFor();
        assert.equal(await page.locator('[data-ocr-count]').textContent(), '1 of 1 image attached');
        assert.equal(await page.evaluate(() => window.embeddedCameraRequests), 0);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), device + ' ' + route);
        assert.equal(await page.locator('form.registration-editor input[data-ocr-photo]').count(), 0);
        results.push({device, route, nativeCaptureRouting:true, gallerySeparate:true, independentSides:true, receipt:true, cancelRetainsImage:true});
      }
      await context.close();
    }
    const context = await browser.newContext();
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    for (const route of ['pdao', 'onsite-pdao']) {
      await page.goto(base + '/' + route + '.html');
      await page.locator('[data-document-ocr]:visible').waitFor();
      for (const width of [1440, 932, 390, 320]) {
        await page.setViewportSize({width, height:1100});
        for (const theme of ['light', 'dark']) {
          await page.evaluate(theme => {document.documentElement.dataset.publicTheme=theme; document.documentElement.dataset.dashboardTheme=theme;}, theme);
          await page.waitForFunction(theme => {
            const style = getComputedStyle(document.querySelector('[data-ocr-kind]'));
            return style.borderRadius === '16px' && style.backgroundColor === (theme === 'dark' ? 'rgb(25, 24, 23)' : 'rgb(255, 255, 255)');
          }, theme);
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'overflow ' + route + width);
          await page.locator('[data-document-ocr]').screenshot({path:path.join(output, `${route}-${width}-${theme}.png`)});
        }
      }
      const documents = page.locator('fieldset, section').filter({has:page.locator('[name=photo_2x2]')}).last();
      await documents.screenshot({path:path.join(output, route + '-uploads-mobile.png')});
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({results, errors}, null, 2));
    console.log(JSON.stringify({passed:results.length, errors, output}));
  } finally {await browser.close(); await new Promise(resolve => server.close(resolve));}
})().catch(error => {console.error(error); process.exitCode=1; server.close();});
