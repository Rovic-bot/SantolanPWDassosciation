const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const output = process.argv[2];
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 1200}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const name of ['filled', 'minimal', 'long', 'receipt']) {
      await page.goto(pathToFileURL(path.join(output, `${name}.html`)).href);
      await page.evaluate(() => document.fonts.ready);
      assert(await page.locator('img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0)));
      if (name === 'receipt') {
        for (const width of [1440, 768, 390, 320]) {
          await page.setViewportSize({width, height: 1000});
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `receipt overflow at ${width}px`);
          assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(7, 18, 37)');
          assert(await page.getByRole('heading', {name: 'Application received.', exact: true}).isVisible());
          await page.screenshot({path: path.join(output, `receipt-screen-${width}.png`)});
        }
        await page.setViewportSize({width: 1440, height: 1000});
        await page.locator('summary').click();
        assert(await page.getByText('Print on A4 paper at 100% scale', {exact: false}).isVisible());
        await page.locator('summary').click();
        await page.locator('.pdao-view-form').click();
        assert.equal(new URL(page.url()).hash, '#submitted-form');
        assert.equal(await page.locator('.pdao-finish form').getAttribute('method'), 'post');
        assert.equal(await page.locator('.pdao-finish input[name="csrfmiddlewaretoken"]').count(), 1);
      }
      await page.emulateMedia({media: 'print'});
      const heights = await page.locator('.pdao-sheet').evaluateAll(sheets => sheets.map(sheet => sheet.getBoundingClientRect().height));
      const pdf = await page.pdf({path: path.join(output, `${name}.pdf`), preferCSSPageSize: true,
        printBackground: true, displayHeaderFooter: false});
      const pages = (pdf.toString('latin1').match(/\/Type \/Page\b/g) || []).length;
      if (name !== 'long') {
        assert.equal(pages, 2, `${name}: expected two A4 pages, got ${pages}; sheet heights ${heights}`);
        assert(heights.every(height => height < 1124), `${name}: page exceeds A4`);
      }
      for (let index = 0; index < 2; index++) {
        await page.locator('.pdao-sheet').nth(index).screenshot({path: path.join(output, `${name}-page-${index + 1}.png`)});
      }
      assert.equal(await page.locator('.registration-controls').isVisible(), false);
      assert(await page.locator('.pdao-receipt-reference').isVisible());
      assert((await page.locator('.pdao-receipt-reference').innerText()).includes(name === 'receipt' ? 'PDAO-00000000-0000-4000-8000-000000000001' : 'PDAO-000001'));
      if (name === 'receipt') {
        assert.equal(await page.locator('.pdao-screen-only').evaluateAll(elements => elements.some(el => getComputedStyle(el).display !== 'none')), false);
        assert.equal(await page.locator('.pdao-sheet').first().evaluate(el => getComputedStyle(el).color), 'rgb(17, 17, 17)');
        assert.equal(await page.locator('.pdao-sheet').first().evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(255, 255, 255)');
      }
      assert.equal(await page.locator('[data-pdao-options="submission_channel"] .is-checked').count(), 1);
      assert.equal(await page.locator('.pdao-cell, .pdao-family td').evaluateAll(cells =>
        cells.filter(cell => cell.scrollWidth > cell.clientWidth + 2).length), 0, `${name}: text overflow`);
      await page.emulateMedia({media: 'screen'});
      await page.evaluate(() => { window.printCalls = 0; window.print = () => window.printCalls++; });
      await page.locator('[data-registration-print]').click();
      assert.equal(await page.evaluate(() => window.printCalls), 1);
      await page.setViewportSize({width: 390, height: 844});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path: path.join(output, `${name}-mobile.png`)});
      await page.setViewportSize({width: 1100, height: 1200});
      console.log(`${name}: ${pages} printed pages; images, checkboxes, wrapping, mobile and print control passed.`);
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
