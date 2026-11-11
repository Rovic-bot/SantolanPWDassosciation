const path = require('path'), fs = require('fs'), assert = require('assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || runtime);
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const output = path.join(__dirname, '../.local/qa-public-navigation');
  fs.mkdirSync(output, {recursive: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const routes = ['/', '/about/', '/announcements/', '/events/', '/programs/', '/results/', '/membership/register/'];
    const names = ['Home', 'About', 'Announcements', 'Events', 'Programs', 'Results', 'Membership'];
    const anchors = ['application-information', 'contact', 'faq', 'ewaf', 'privacy', 'accessibility'];
    const go = async route => assert.equal((await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'})).status(), 200);
    const checkOverflow = async label => {
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      if (overflow) {
        await page.screenshot({path: path.join(output, 'overflow.png'), fullPage: true});
        console.log(JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('body *')].filter(element => {
          const rect = element.getBoundingClientRect(); return rect.width && (rect.right > innerWidth + 1 || rect.left < -1);
        }).map(element => ({tag: element.tagName, class: element.className, width: element.getBoundingClientRect().width})))));
      }
      assert.equal(overflow, false, label);
    };
    for (let index = 0; index < routes.length; index++) {
      await go(routes[index]);
      const links = page.locator('#public-nav .nav-link');
      assert.deepEqual((await links.allTextContents()).map(text => text.replace('↗', '').trim()), names);
      assert.equal((await page.locator('#public-nav [aria-current="page"]').innerText()).replace('↗', '').trim(), names[index]);
      for (const width of [320, 390, 768, 1024, 1440]) {
        await page.setViewportSize({width, height: 900});
        await checkOverflow(`${names[index]} at ${width}`);
      }
      await page.screenshot({path: path.join(output, names[index].toLowerCase() + '-desktop.png'), fullPage: true});
    }
    await page.setViewportSize({width: 390, height: 850});
    await go('/');
    const menu = page.getByRole('button', {name: 'Toggle navigation'});
    await menu.click();
    await page.locator('#public-nav.show').waitFor();
    await page.getByRole('navigation', {name: 'Main navigation'}).getByRole('link', {name: 'Programs', exact: true}).focus();
    await page.keyboard.press('Escape');
    assert.equal(await menu.getAttribute('aria-expanded'), 'false');
    assert.equal(await menu.evaluate(element => element === document.activeElement), true);
    for (const anchor of anchors) {
      await page.locator(`.home-help-shortcuts a[href="#${anchor}"]`).click();
      assert.equal(new URL(page.url()).hash, '#' + anchor);
      const target = page.locator('#' + anchor);
      assert.equal(await target.evaluate(element => element === document.activeElement), true);
      const top = await target.evaluate(element => element.getBoundingClientRect().top);
      const headerBottom = await page.locator('.site-header').evaluate(element => element.getBoundingClientRect().bottom);
      assert.ok(top >= headerBottom - 1, `unobscured ${anchor}: ${top} >= ${headerBottom}`);
      await checkOverflow(`Home section ${anchor}`);
    }
    await go('/information/privacy/');
    assert.equal(new URL(page.url()).hash, '#privacy');
    await page.screenshot({path: path.join(output, 'home-privacy-mobile.png')});
    await page.evaluate(() => {document.documentElement.style.fontSize = '200%'; document.documentElement.dataset.contrast = 'true';});
    await page.setViewportSize({width: 320, height: 850});
    await checkOverflow('Home enlarged text and high contrast at 320px');
    await page.screenshot({path: path.join(output, 'home-enlarged-mobile.png'), fullPage: true});
    // Guidance and anchors remain usable with scripting unavailable.
    const noScript = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 850}});
    const plain = await noScript.newPage();
    await plain.goto(process.env.QA_URL + '/');
    for (const anchor of anchors) assert.equal(await plain.locator('#' + anchor).isVisible(), true);
    await noScript.close();
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({result: 'passed', pages: 7, widths: [320,390,768,1024,1440], homeSections: 6, keyboard: true, enlargedText: true, noScript: true, javascriptErrors: 0}));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exit(1);});
