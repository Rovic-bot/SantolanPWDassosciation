const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}});
    await context.addCookies([{name: 'sessionid', value: process.env.QA_ADMIN_SESSION, url: process.env.QA_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const styles = {};
    for (const [name, route] of [['association', process.env.QA_ASSOCIATION_ROUTE], ['pdao', process.env.QA_PDAO_ROUTE]]) {
      await page.goto(process.env.QA_URL + route);
      await page.locator('.registration-inbox [data-auto-filter-ready]').waitFor();
      assert.equal(await page.locator('select[name=channel]').count(), 0);
      assert.equal(await page.getByRole('link', {name: 'Record printed form'}).count(), 0);
      for (const theme of ['dark', 'light']) {
        await page.evaluate(value => { localStorage.setItem('santolan-dashboard-theme', value); document.documentElement.dataset.dashboardTheme = value; }, theme);
        styles[`${name}-${theme}`] = await page.locator('.registration-inbox-filters').evaluate(el => {
          const style = getComputedStyle(el);
          return [style.backgroundColor, style.backgroundImage, style.borderColor, style.borderRadius];
        });
        for (const width of [1600, 1024, 768, 390, 320]) {
          await page.setViewportSize({width, height: 1000});
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name} ${theme} ${width}: overflow`);
          const select = await page.locator('select[name=state]').boundingBox();
          assert(select.x >= 0 && select.x + select.width <= width + 1, 'Filter stays inside viewport');
          if ([1600, 390].includes(width)) await page.screenshot({path: path.join(process.env.QA_OUTPUT, `${name}-${theme}-${width}.png`), fullPage: true});
        }
      }
    }
    for (const theme of ['dark', 'light']) assert.deepEqual(styles[`association-${theme}`], styles[`pdao-${theme}`]);
    await page.setViewportSize({width: 1600, height: 1000});
    await page.locator('#pdao-state').selectOption('ready');
    await page.getByText('No PDAO applications match this search.').waitFor();
    await page.locator('.registration-inbox-tabs a').filter({hasText: 'All applications'}).click();
    await page.locator('.registration-inbox-name').waitFor();
    await page.locator('#pdao-search').fill('No such applicant');
    await page.getByText('No PDAO applications match this search.').waitFor();
    await page.locator('.registration-inbox-clear').click();
    await page.locator('.registration-inbox-name').waitFor();
    assert.equal(await page.locator('.registration-inbox-name').count(), 1);

    await page.goto(process.env.QA_URL + process.env.QA_PROGRAM_ROUTE);
    await page.locator('.catalog-photo-card').first().waitFor();
    const featured = page.locator('.catalog-photo-card').filter({has: page.getByRole('heading', {name: 'Community mobility support', exact: true})});
    assert.equal(await page.locator('.catalog-photo-card').count(), 3);
    await featured.locator('img').scrollIntoViewIfNeeded();
    await featured.locator('img').evaluate(img => img.decode());
    assert.equal(await featured.locator('h3 a').evaluate(el => getComputedStyle(el).color), 'rgb(255, 255, 255)');
    assert.equal(await featured.locator('.public-program-artwork').evaluate(el => getComputedStyle(el).position), 'absolute');
    const mobileSizes = [];
    for (const width of [1600, 1024, 768, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      await page.locator('.catalog-grid').scrollIntoViewIfNeeded();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `program cards ${width}: overflow`);
      for (const card of await page.locator('.catalog-photo-card').all()) {
        assert(await card.evaluate(el => el.scrollWidth <= el.clientWidth + 1 && el.scrollHeight <= el.clientHeight + 1), 'Card content fits');
        const cardBox = await card.boundingBox(), link = await card.locator('.catalog-card-link').boundingBox();
        assert(link.height >= 44 && link.y + link.height <= cardBox.y + cardBox.height, 'CTA stays visible inside card');
        assert(await card.evaluate(el => {
          const initials = el.querySelector('.public-program-initials');
          if (initials.hidden) return true;
          const range = document.createRange();
          range.selectNodeContents(initials);
          return range.getBoundingClientRect().bottom + 8 <= el.querySelector('h3').getBoundingClientRect().top;
        }), 'Fallback initials do not overlap the title');
      }
      mobileSizes.push({width, cardWidth: (await featured.boundingBox()).width});
      if ([1600, 390].includes(width)) await page.screenshot({path: path.join(process.env.QA_OUTPUT, `programs-${width}.png`)});
    }
    await featured.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert(await featured.locator('details').evaluate(el => el.open));
    await page.evaluate(() => document.documentElement.dataset.contrast = 'true');
    assert.equal(await featured.locator('.catalog-card-link').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(0, 0, 0)');
    await page.evaluate(() => delete document.documentElement.dataset.contrast);
    await featured.locator('.catalog-card-link').click();
    await page.getByRole('heading', {name: 'Community mobility support', exact: true}).waitFor();
    assert.equal(errors.length, 0, errors.join('\n'));
    fs.writeFileSync(path.join(process.env.QA_OUTPUT, 'checks.json'), JSON.stringify({errors, styles, mobileSizes, filters: 'passed', links: 'passed'}, null, 2));
    console.log('Desktop/mobile cards, imagery, fallback, schedule, CTA, contrast, both themes, shared lists, automatic search/status filters passed.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
