/* Address-menu interaction checks on actual rendered forms. Never submit. */
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = process.cwd(), fixtures = process.env.INTAKE_FIXTURES;
const output = process.env.INTAKE_ARTIFACT_DIR || path.join(root, '.local/address-dropdown-browser');
fs.mkdirSync(output, {recursive: true});

(async () => {
  let server, base = process.env.INTAKE_URL;
  if (!base) {
    assert(fixtures, 'Render the four form fixtures with registration_validation_checks.py first.');
    server = http.createServer((req, res) => {
      const url = new URL(req.url, 'http://localhost');
      const file = path.resolve(url.pathname.startsWith('/static/') ? root : fixtures, '.' + url.pathname);
      if (req.method !== 'GET' || (!file.startsWith(root + path.sep) && !file.startsWith(path.resolve(fixtures) + path.sep))) {
        res.writeHead(403); res.end(); return;
      }
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {res.writeHead(404); res.end(); return;}
      const types = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json',
        '.png': 'image/png', '.svg': 'image/svg+xml', '.webp': 'image/webp'};
      res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'});
      fs.createReadStream(file).pipe(res);
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    base = 'http://127.0.0.1:' + server.address().port;
  }
  const routes = process.env.INTAKE_URL ? [
    '/membership/registration/apply/', '/membership/registration/pdao/apply/',
    ...(process.env.INTAKE_STORAGE_STATE ? ['/membership/applications/new/', '/membership/registration/pdao/onsite/'] : []),
  ] : ['/association.html', '/pdao.html', '/onsite-association.html', '/onsite-pdao.html'];
  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  const checks = [], errors = [], posts = [];
  let page;
  try {
    const context = await browser.newContext({hasTouch: true, reducedMotion: 'reduce',
      storageState: process.env.INTAKE_STORAGE_STATE});
    await context.route('**/*', route => {
      if (!['GET', 'HEAD'].includes(route.request().method())) {posts.push(route.request().method()); return route.abort();}
      return route.continue();
    });
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    const input = name => page.locator('[name=' + name + ']');
    const list = name => page.locator('#id_' + name + '_addresses');
    const visibleMenu = () => page.locator('.registration-address-menu:not([hidden])');
    async function select(name, search, label, touch = false) {
      await input(name).fill(search);
      const option = list(name).getByRole('option', {name: label, exact: true});
      await option.waitFor({state: 'visible'});
      if (touch) await option.tap(); else await option.click();
      assert.equal(await input(name).inputValue(), label);
      assert.equal(await input(name).getAttribute('aria-expanded'), 'false');
      assert.equal(await input(name).evaluate(node => document.activeElement === node), true);
    }
    async function bounds(name) {
      await visibleMenu().waitFor({state: 'visible'});
      const menu = await visibleMenu().boundingBox(), field = await input(name).boundingBox();
      const viewport = page.viewportSize();
      assert(menu.x >= 0 && menu.y >= 0 && menu.x + menu.width <= viewport.width + 1 &&
        menu.y + menu.height <= viewport.height + 1, 'Menu stays in viewport: ' + JSON.stringify(menu));
      assert(Math.abs(menu.width - field.width) <= 1, 'Menu aligns with its input');
      const readable = await visibleMenu().evaluate(node => {
        const style = getComputedStyle(node);
        return style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.color !== style.backgroundColor;
      });
      assert(readable, 'Opaque surface with contrasting text');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    }
    for (const [routeIndex, route] of routes.entries()) {
      await page.goto(base + route, {waitUntil: 'networkidle'});
      await page.waitForFunction(() => document.querySelector('[name=city]')?.dataset.addressCount === '1642');
      const privacy = page.locator('[data-registration-privacy-open]');
      if (await privacy.isVisible()) {
        await privacy.click();
        await page.locator('[data-registration-privacy-close]').click();
      }
      assert.equal(await input('city').getAttribute('role'), 'combobox');
      assert.equal(await input('city').getAttribute('list'), null);
      await input('barangay').fill('');
      assert.match(await visibleMenu().textContent(), /Select a city/);
      await input('city').fill('Pasig');
      await input('city').press('ArrowDown');
      const activeId = await input('city').getAttribute('aria-activedescendant');
      assert.equal(await page.locator('#' + activeId).textContent(), 'City of Pasig');
      await input('city').press('Enter');
      assert.equal(await input('city').inputValue(), 'City of Pasig');
      assert.equal(await input('city').getAttribute('aria-expanded'), 'false');
      await page.waitForFunction(() => document.querySelector('[name=barangay]').dataset.addressCount === '30');
      assert.equal(await input('region').inputValue(), 'National Capital Region (NCR)');
      await select('barangay', 'Sant', 'Santolan', true);
      await select('city', 'San Juan Abra', 'San Juan (Abra)');
      await page.waitForFunction(() => document.querySelector('[name=barangay]').dataset.addressCount !== '0');
      assert.equal(await input('barangay').inputValue(), '');
      assert.equal(await input('region').inputValue(), 'Cordillera Administrative Region (CAR)');
      if (await input('province').count()) assert.equal(await input('province').inputValue(), 'Abra');
      await select('city', 'Manila', 'City of Manila');
      await page.waitForFunction(() => Number(document.querySelector('[name=barangay]').dataset.addressCount) > 800);
      await input('barangay').fill('');
      assert.equal(await list('barangay').getByRole('option').count(), 50);
      await input('barangay').press('ArrowUp');
      assert(await list('barangay').evaluate(node => node.scrollTop > 0), 'Keyboard scrolls a long list');
      await input('barangay').press('Escape');
      assert.equal(await input('barangay').inputValue(), '');
      assert.equal(await input('barangay').getAttribute('aria-activedescendant'), null);
      await input('city').fill('No such city zzzz');
      assert.match(await visibleMenu().textContent(), /No matching addresses/);
      await input('city').press('Tab');
      assert.equal(await input('city').inputValue(), 'No such city zzzz');
      assert.equal(await input('city').getAttribute('aria-expanded'), 'false');
      await select('city', 'Pasig', 'City of Pasig');
      await page.waitForFunction(() => document.querySelector('[name=barangay]').dataset.addressCount === '30');

      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({width, height: 850});
        for (const theme of ['light', 'dark', 'contrast']) {
          await page.evaluate(theme => {
            document.documentElement.dataset.publicTheme = theme === 'dark' ? 'dark' : 'light';
            document.documentElement.dataset.dashboardTheme = theme === 'dark' ? 'dark' : 'light';
            document.documentElement.dataset.contrast = String(theme === 'contrast');
          }, theme);
          const fields = [['city', 'San Juan'], ['barangay', 'San'], ['region', 'Region'],
            ...(await input('province').count() ? [['province', 'Metro']] : [])];
          for (const [name, search] of fields) {
            await input(name).fill(search);
            await bounds(name);
            await input(name).press('ArrowDown');
            assert(await input(name).getAttribute('aria-activedescendant'));
            if (name === 'city' && width !== 320) await page.screenshot({path: path.join(output, `${routeIndex}-${width}-${theme}.png`)});
            await input(name).press('Escape');
            // Restore a valid city without discarding the next field's available suggestions.
            if (name === 'city') {
              await select('city', 'Pasig', 'City of Pasig');
              await page.waitForFunction(() => document.querySelector('[name=barangay]').dataset.addressCount === '30');
            }
          }
          checks.push({route, width, theme, addressMenus: fields.length});
        }
      }
      // A short viewport models the space left when a phone's keyboard is open.
      await page.setViewportSize({width: 390, height: 330});
      await input('city').fill('San Juan');
      await bounds('city');
      await select('city', 'Pasig', 'City of Pasig', true);
      await page.waitForFunction(() => document.querySelector('[name=barangay]').dataset.addressCount === '30');
      await input('city').fill('San');
      await page.evaluate(() => window.WorkspacePage.replace());
      assert.equal(await page.locator('.registration-address-menu').count(), 0, 'Workspace navigation disposes menus');
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(posts, []);
    fs.writeFileSync(path.join(output, 'dropdown-results.json'), JSON.stringify({checks, errors, applicationPosts: posts}, null, 2));
    console.log(JSON.stringify({scenarios: checks.length, routes: routes.length, errors, applicationPosts: posts}));
    await context.close();
  } catch (error) {
    if (page) {
      await page.screenshot({path: path.join(output, 'failure.png')});
      console.error(JSON.stringify(await page.evaluate(() => ({
        focused: document.activeElement?.getAttribute('name'),
        fields: [...document.querySelectorAll('[role=combobox]')].map(node => ({name: node.name,
          expanded: node.getAttribute('aria-expanded'), box: node.getBoundingClientRect().toJSON()})),
      }))));
    }
    throw error;
  } finally {
    await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
