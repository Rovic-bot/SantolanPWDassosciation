/* Synthetic, read-only browser checks. Application submissions are blocked. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = process.cwd(), fixtures = process.env.INTAKE_FIXTURES;
const output = process.env.INTAKE_ARTIFACT_DIR || path.join(root, '.local/intake-browser');
fs.mkdirSync(output, {recursive: true});
(async () => {
  let server, base = process.env.INTAKE_URL;
  if (!base) {
    assert(fixtures);
    server = http.createServer((req, res) => {
      const url = new URL(req.url, 'http://localhost');
      const file = url.pathname.startsWith('/static/') ? path.join(root, url.pathname) : path.join(fixtures, url.pathname);
      if (req.method !== 'GET' || (!file.startsWith(root + path.sep) && !file.startsWith(path.resolve(fixtures) + path.sep))) {
        res.writeHead(403); res.end(); return;
      }
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {res.writeHead(404); res.end(); return;}
      const type = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json',
        '.png': 'image/png', '.svg': 'image/svg+xml'}[path.extname(file)] || 'application/octet-stream';
      res.writeHead(200, {'Content-Type': type}); fs.createReadStream(file).pipe(res);
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    base = 'http://127.0.0.1:' + server.address().port;
  }
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const checks = [], errors = [], blocked = [];
  const routes = process.env.INTAKE_URL ?
    ['/membership/registration/apply/', '/membership/registration/pdao/apply/'] :
    ['/association.html', '/pdao.html', '/onsite-association.html', '/onsite-pdao.html'];
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  await context.route('**/*', route => {
    if (route.request().method() !== 'GET') {blocked.push(route.request().method()); return route.abort();}
    return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const change = async (name, value) => {
    await page.locator('[name="' + name + '"]').fill(value);
    await page.locator('[name="' + name + '"]').dispatchEvent('change');
  };
  async function open(route) {
    await page.goto(base + route);
    await page.waitForFunction(() => document.querySelectorAll('#id_city_addresses option').length === 1642);
    const privacy = page.locator('[data-registration-privacy-open]');
    if (await privacy.isVisible()) {
      await privacy.click();
      await page.locator('[data-registration-privacy-close]').click();
    }
  }
  try {
    for (const [index, route] of routes.entries()) {
      await open(route);
      await change('city', 'Manila');
      await page.waitForFunction(() => document.querySelectorAll('#id_barangay_addresses option').length > 800);
      assert.equal(await page.locator('[name=city]').inputValue(), 'City of Manila');
      assert.equal(await page.locator('[name=region]').inputValue(), 'National Capital Region (NCR)');
      await change('barangay', 'Barangay 1');
      await change('region', 'Region III (Central Luzon)');
      assert.equal(await page.locator('[name=region]').evaluate(input => input.checkValidity()), false);
      await change('city', 'Pasig City');
      await page.waitForFunction(() => document.querySelectorAll('#id_barangay_addresses option').length === 30);
      assert.equal(await page.locator('[name=barangay]').inputValue(), '');
      await change('barangay', 'Santolan');
      assert.equal(await page.locator('[name=barangay]').evaluate(input => input.checkValidity()), true);
      await change('barangay', 'Barangay 1');
      assert.equal(await page.locator('[name=barangay]').evaluate(input => input.checkValidity()), false);
      await change('barangay', 'Santolan');
      const mobile = page.locator('[name=contact_number]');
      await mobile.fill('');
      await mobile.pressSequentially('098765432100XYZ');
      assert.equal(await mobile.inputValue(), '9876543210');
      assert.equal(await mobile.evaluate(input => input.checkValidity()), true);
      await mobile.fill('9071234567');
      assert.equal(await mobile.inputValue(), '9071234567');
      await mobile.fill('917');
      assert.equal(await mobile.evaluate(input => input.checkValidity()), false);
      await mobile.fill('9071234567');
      // OCR/paste formatted phone stays compatible with the new +63 field.
      await mobile.evaluate(input => {input.value = '09171234567'; input.dispatchEvent(new Event('input', {bubbles: true}));});
      assert.equal(await mobile.inputValue(), '9171234567');
      const born = page.locator('[name=birthdate]');
      const max = await born.getAttribute('max');
      await born.fill(max);
      assert.equal(await born.evaluate(input => input.checkValidity()), true);
      await born.fill('2099-01-01');
      assert.equal(await born.evaluate(input => input.checkValidity()), false);
      await born.fill('1990-01-02'); await born.dispatchEvent('change');
      assert.match(await page.locator('[data-registration-age]').textContent(), /^3[6-9] years$/);
      const pdao = await page.locator('[name=application_type]').count();
      const education = page.locator('[name=education]'), employment = page.locator('[name=employment_status]');
      const adultEducation = await education.locator('option').allTextContents();
      await education.selectOption(pdao ? 'College' : 'College Undergraduate');
      await employment.selectOption(pdao ? 'Employed' : 'employed');
      if (pdao) await page.locator('[name=occupation]').selectOption('Professional');
      await change('birthdate', max);
      assert.equal(await education.inputValue(), '');
      assert.equal(await employment.inputValue(), '');
      assert.deepEqual(await education.locator('option').allTextContents(),
        ['Select an option', pdao ? 'None' : 'None / Not yet in school', 'Kindergarten', 'Elementary']);
      assert.deepEqual((await employment.locator('option').allTextContents()).sort(), ['Select an option', 'Student', 'Unemployed'].sort());
      await employment.selectOption(pdao ? 'Student' : 'student');
      await education.selectOption('Kindergarten');
      if (pdao) {
        for (const name of ['employment_category', 'employment_nature', 'occupation', 'occupation_other']) {
          assert.equal(await page.locator('[name=' + name + ']').isDisabled(), true);
          assert.equal(await page.locator('[name=' + name + ']').inputValue(), '');
        }
        for (const name of ['father_first_name', 'father_last_name', 'mother_first_name', 'mother_last_name'])
          assert.equal(await page.locator('[name=' + name + ']').evaluate(input => input.required), true);
        for (const name of ['father_middle_name', 'mother_middle_name'])
          assert.equal(await page.locator('[name=' + name + ']').evaluate(input => input.required), false);
      }
      const today = await born.getAttribute('data-intake-today');
      const fifteen = (Number(today.slice(0, 4)) - 15) + today.slice(4);
      const almostFifteen = new Date(fifteen + 'T12:00:00Z');
      almostFifteen.setUTCDate(almostFifteen.getUTCDate() + 1);
      await change('birthdate', almostFifteen.toISOString().slice(0, 10));
      assert.equal(await education.locator('option').count(), 4);
      await change('birthdate', fifteen);
      assert.deepEqual(await education.locator('option').allTextContents(), adultEducation);
      assert.equal(await employment.inputValue(), pdao ? 'Student' : 'student');
      assert(await employment.locator('option').count() > 3);
      if (pdao) assert.equal(await page.locator('[name=occupation]').isEnabled(), true);
      await change('birthdate', max);
      await education.scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(output, 'child-options-' + index + '.png')});
      await change('birthdate', '1990-01-02');
      if (await page.locator('[name=spouse_name]').count()) {
        await page.locator('[name=civil_status]').selectOption('Married');
        assert.equal(await page.locator('[name=spouse_name]').evaluate(input => input.required), true);
        assert.equal(await page.locator('[name=spouse_contact]').evaluate(input => input.required), true);
        await page.locator('[name=civil_status]').selectOption('Single');
        assert.equal(await page.locator('[name=spouse_name]').evaluate(input => input.required), false);
      } else {
        assert.equal(await page.locator('[name=date_applied]').isDisabled(), true);
        assert.equal(await page.locator('[name=date_applied]').inputValue(), await born.getAttribute('data-intake-today'));
        const boxes = page.locator('[name=disability_types]');
        assert.equal(await boxes.first().evaluate(input => input.checkValidity()), false);
        await boxes.first().check();
        assert.equal(await boxes.first().evaluate(input => input.checkValidity()), true);
        assert.equal(await page.locator('[name=email]').evaluate(input => input.required), true);
        assert.equal(await page.locator('[name=province]').inputValue(), 'Metro Manila (NCR - no province)');
      }
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, route + ' overflow ' + width);
      }
      await page.setViewportSize({width: index % 2 ? 390 : 1440, height: 1000});
      await page.locator('[name=city]').scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(output, 'address-' + index + '.png')});
      checks.push({route, address: true, mobile: true, minimumAge: true, requiredFields: true,
        under15EducationAndEmployment: true, fifteenthBirthdayRestoresChoices: true, familyNames: pdao ? true : 'existing family fields', widths: [1440, 390, 320]});
    }
    // Progressive fallback: typed values remain possible if catalogue loading fails.
    await context.route('**/data/psgc-2026-q2/**', route => route.abort());
    await page.goto(base + routes[0]);
    await page.waitForFunction(() => document.body.textContent.includes('Address suggestions could not load'));
    assert.equal(await page.locator('[name=city]').isEnabled(), true);
    checks.push({addressDownloadFailure: 'Manual input remains available; server validation applies'});
    const nojs = await browser.newContext({javaScriptEnabled: false});
    const plain = await nojs.newPage();
    await plain.goto(base + routes[0]);
    assert.equal(await plain.locator('[name=city]').isEnabled(), true);
    assert.equal(await plain.locator('[name=contact_number]').getAttribute('maxlength'), '10');
    checks.push({noJavaScript: 'Form and server validation retained'});
    await nojs.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(blocked, []);
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({checks, errors, applicationPosts: blocked}, null, 2));
    console.log(JSON.stringify({checks: checks.length, errors, applicationPosts: blocked}));
  } finally {
    await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
