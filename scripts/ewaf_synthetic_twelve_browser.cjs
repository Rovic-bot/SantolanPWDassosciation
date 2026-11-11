/* Read-only browser checks against the synthetic Django live-test server. */
const path = require('path');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const origin = new URL(process.env.QA_URL);
  assert(['localhost', '127.0.0.1'].includes(origin.hostname));
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
    // No browser requests can leave the disposable loopback server.
    await context.route('**/*', route => new URL(route.request().url()).origin === origin.origin
      ? route.continue() : route.abort());
    await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: origin.origin}]);
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const route = `/ewaf/programs/${process.env.QA_PROGRAM}/`;
    const response = await page.goto(origin.origin + route, {waitUntil: 'networkidle'});
    assert.equal(response.status(), 200);
    assert(response.headers()['cache-control'].includes('no-store'));
    assert.equal(await page.locator('#results table tbody tr').count(), 12);
    const body = await page.locator('main').innerText();
    for (const name of ['Ana', 'Ben', 'Cora', 'Dan', 'Ella', 'Finn', 'Gia', 'Hugo', 'Iris', 'Jiro', 'Kara', 'Luis']) {
      assert(body.includes(name), name);
    }
    const expected = JSON.parse(process.env.QA_EXPECTED);
    for (const row of await page.locator('#results table tbody tr').all()) {
      const name = await row.locator('th a').innerText();
      const cells = await row.locator('td').allTextContents();
      assert.equal(parseInt(cells[0], 10), expected[name].rank, name);
      assert.equal(cells[1].trim(), expected[name].score, name);
    }
    assert.equal(await page.locator('[name=score], [name=rank]').count(), 0);
    await page.locator('#results').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, `${process.env.QA_SCENARIO}-ranking.png`), fullPage: true});
    await page.locator('#results').screenshot({path: path.join(process.env.QA_OUTPUT, `${process.env.QA_SCENARIO}-ranking-table.png`)});
    const guide = await page.goto(origin.origin + route + 'calculation-guide/', {waitUntil: 'networkidle'});
    assert.equal(guide.status(), 200);
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, `${process.env.QA_SCENARIO}-calculation-guide.png`), fullPage: true});
    for (const width of [390, 1440]) {
      await page.setViewportSize({width, height: 1000});
      await page.goto(origin.origin + route, {waitUntil: 'networkidle'});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    }
    const vault = await page.goto(origin.origin + '/ewaf/vault/', {waitUntil: 'networkidle'});
    assert.equal(vault.status(), 200);
    const proposal = JSON.parse(process.env.QA_PROPOSAL);
    const sliders = page.locator('#weight-bars input[type=range]');
    assert.equal(await sliders.count(), 4);
    assert.deepEqual(await sliders.evaluateAll(inputs => inputs.map(input => input.id)),
      proposal.order.map(code => `weight-${code}`));
    for (const code of proposal.order) {
      assert.equal(Number(await page.locator(`#weight-${code}`).inputValue()), proposal.weights[code] / 100);
    }
    const second = proposal.order[1];
    await page.locator(`[data-criterion="${second}"] .weight-order button`).first().click();
    assert.equal(await sliders.first().getAttribute('id'), `weight-${second}`);
    await page.locator('#reset-weights').click();
    assert.deepEqual(await sliders.evaluateAll(inputs => inputs.map(input => input.id)),
      proposal.order.map(code => `weight-${code}`));
    await page.locator('#preview-weights').click();
    await page.locator('#weight-preview').waitFor({state: 'visible'});
    assert.equal(await page.locator('#weight-preview-rows tr').count(), 4);
    for (const row of await page.locator('#weight-preview-rows tr').all()) {
      const cells = await row.locator('td').allTextContents();
      assert.equal(cells[1], cells[2], 'The five requested vectors must have equal proposed and calculated percentages.');
    }
    await page.screenshot({path: path.join(process.env.QA_OUTPUT, `${process.env.QA_SCENARIO}-vault.png`), fullPage: true});
    assert.deepEqual(errors, []);
    console.log(`Synthetic ${process.env.QA_SCENARIO}: 12 Admin rows, private headers, guide, 390/1440 widths, no JS errors.`);
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exit(1);});
