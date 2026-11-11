/* Read-only browser checks using HTML emitted by analytics' isolated fixture test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = process.cwd();
const fixtures = path.join(root, '.local/dashboard-charts-20261029');
const output = path.join(root, 'docs/dashboard-chart-variety-2026-10-29');
const base = process.env.DASHBOARD_BASE_URL || 'http://127.0.0.1:8013';
const expected = JSON.parse(fs.readFileSync(path.join(fixtures, 'expected.json'), 'utf8'));
fs.mkdirSync(output, {recursive:true});

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], blocked = [];
  async function context(options = {}) {
    const ctx = await browser.newContext({viewport:{width:1440,height:1100}, ...options});
    await ctx.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== base || request.method() !== 'GET') {
        blocked.push(request.method() + ' ' + url.pathname); return route.abort();
      }
      if (url.pathname === '/dashboard/') {
        const name = url.searchParams.get('fixture') || (url.searchParams.has('period') ? 'filtered' : 'after');
        return route.fulfill({contentType:'text/html; charset=utf-8', body:fs.readFileSync(path.join(fixtures,name+'.html'))});
      }
      await route.continue();
    });
    return ctx;
  }
  const overflow = page => page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  try {
    const ctx = await context(); const page = await ctx.newPage();
    page.on('pageerror', error => errors.push(error.message));
    for (const width of [1440, 1024, 768, 390, 320]) {
      await page.setViewportSize({width,height:1100});
      await page.goto(base + '/dashboard/?fixture=after');
      await page.waitForLoadState('networkidle');
      assert.equal(await page.locator('.overview-metric').count(), 6);
      assert.equal(await page.locator('.overview-section').count(), 10);
      assert.equal(await page.locator('.overview-visual svg').count(), 9);
      assert.equal(await page.locator('.overview-heatmap').count(), 1);
      assert.equal(await page.locator('[data-chart-fallback]:visible').count(), 0);
      assert(!await overflow(page), 'Page overflow at '+width);
      const clipped = await page.locator('.overview-visual svg').evaluateAll(svgs => svgs.flatMap(svg => {
        const bounds = svg.getBoundingClientRect();
        return [...svg.querySelectorAll('text')].filter(text => {
          const box = text.getBoundingClientRect(); return box.left < bounds.left - 1 || box.top < bounds.top - 1 || box.right > bounds.right + 1 || box.bottom > bounds.bottom + 1;
        }).map(text => text.textContent);
      }));
      assert.deepEqual(clipped, [], 'Clipped chart text at '+width);
      for (const chart of expected.visualizations) {
        const group = page.locator(`[data-visualization="${chart.id}"]`);
        const rows = await group.locator('.overview-data-table tbody tr').evaluateAll(rows =>
          rows.map(row => [...row.querySelectorAll('th,td')].map(cell => cell.textContent.trim())));
        assert.deepEqual(rows, chart.rows, 'Table mismatch: '+chart.id);
        if (chart.kind === 'heatmap') {
          const values = await group.locator('.overview-heatmap td').allTextContents();
          assert.deepEqual(values.map(Number), chart.rows.flatMap(row => row.slice(1).map(Number)));
        } else {
          const payload = await group.locator('script[type="application/json"]').textContent();
          assert.deepEqual(JSON.parse(payload), chart.payload);
          if (chart.kind === 'scatter') {
            const dots = await group.locator('circle[data-x]').evaluateAll(dots => dots.map(dot => [Number(dot.dataset.x), Number(dot.dataset.y)]));
            assert.deepEqual(dots, chart.payload.points.map(point => [point.x,point.y]));
          } else {
            const values = await group.locator('[data-value]').evaluateAll(nodes => nodes.map(node => Number(node.dataset.value)));
            if (chart.kind === 'stacked') assert.equal(values.reduce((sum,n)=>sum+n,0),chart.total);
            else assert.deepEqual(values, chart.payload.series[0].values.filter(n=>chart.kind==='horizontal'?n>0:true));
          }
        }
      }
      if ([1440,390].includes(width)) await page.screenshot({path:path.join(output,`overview-${width}.png`),fullPage:true});
    }
    for (const summary of await page.locator('.overview-data summary').all()) {
      await summary.focus(); await page.keyboard.press('Enter');
      assert(await summary.locator('..').getAttribute('open') !== null);
      assert.equal(await summary.evaluate(node=>getComputedStyle(node).outlineStyle),'solid');
      await page.keyboard.press('Enter');
    }
    await page.setViewportSize({width:1440,height:1100});
    await page.goto(base+'/dashboard/?fixture=after');
    await page.getByLabel('Activity period',{exact:true}).selectOption('custom');
    await page.getByLabel('Start date',{exact:true}).fill('2026-10-29');
    await page.getByLabel('End date',{exact:true}).fill('2026-10-29');
    await page.getByRole('button',{name:'Apply',exact:true}).click();
    await page.waitForURL(/period=custom/);
    assert.equal(await page.evaluate(()=>document.activeElement.id),'overview-refresh');
    assert.equal(await page.locator('.overview-visual svg').count(),9);
    await page.screenshot({path:path.join(output,'filtered.png'),fullPage:true});
    await page.goto(base+'/dashboard/?fixture=empty');
    assert.match(await page.locator('#overview-results').innerText(),/No matching recorded data/);
    await page.screenshot({path:path.join(output,'no-activity.png'),fullPage:true});
    await page.goto(base+'/dashboard/?fixture=after');
    await page.getByRole('button',{name:'Display preferences',exact:true}).click();
    await page.locator('[data-preference="contrast"]').check();
    await page.locator('[data-preference="motion"]').check();
    await page.keyboard.press('Escape');
    await page.waitForTimeout(100);
    const fill = await page.locator('[data-chart="disability-bar"] rect').first().evaluate(el=>getComputedStyle(el).fill);
    assert.equal(fill,'rgb(0, 87, 73)');
    const ratios = await page.evaluate(() => {
      const l = color => {const c=color.match(/\d+(?:\.\d+)?/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;});return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
      const ratio = (a,b) => (Math.max(l(a),l(b))+.05)/(Math.min(l(a),l(b))+.05);
      return [...document.querySelectorAll('.overview-key')].map(node => {const css=getComputedStyle(node);return ratio(css.color,css.backgroundColor);});
    });
    assert(ratios.every(ratio=>ratio>=4.5));
    console.log('Minimum high-contrast legend text ratio:',Math.min(...ratios).toFixed(2)+':1');
    assert.equal(await page.locator('.overview-visual').first().evaluate(el=>getComputedStyle(el).animationName),'none');
    await page.screenshot({path:path.join(output,'high-contrast.png'),fullPage:true});
    await page.setViewportSize({width:320,height:1100});
    await page.evaluate(()=>document.documentElement.style.fontSize='200%');
    await page.waitForTimeout(150);
    assert(!await overflow(page),'200% text page overflow');
    assert.equal(await page.locator('.overview-visual svg').count(),9);
    const font = await page.locator('[data-chart="disability-bar"] text').first().getAttribute('font-size');
    assert(Number(font)>=32,'SVG labels did not enlarge');
    const scrollable = page.locator('.overview-visual[tabindex="0"]').first();
    await scrollable.focus(); await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(150);
    assert(await scrollable.evaluate(node=>node.scrollLeft>0),'Enlarged chart cannot scroll by keyboard');
    await page.screenshot({path:path.join(output,'text-200-percent-320.png'),fullPage:true});
    await page.emulateMedia({forcedColors:'active',reducedMotion:'reduce'});
    const session = await ctx.newCDPSession(page);
    const tree = await session.send('Accessibility.getFullAXTree');
    assert(tree.nodes.some(node=>node.role?.value==='image' && node.name?.value==='Cumulative new memberships'));
    assert(tree.nodes.some(node=>node.role?.value==='table' && node.name?.value.includes('Scheduled events')));
    const noJS = await context({javaScriptEnabled:false,viewport:{width:390,height:1100}});
    const fallback = await noJS.newPage();await fallback.goto(base+'/dashboard/?fixture=after');
    assert.equal(await fallback.locator('.overview-data-table:visible').count(),10);
    assert(!await overflow(fallback));
    await fallback.screenshot({path:path.join(output,'no-javascript.png'),fullPage:true});
    assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
    console.log('PASS: ten populated chart types and all ten tables match synthetic aggregates; six metrics; 1440/1024/768/390/320; keyboard tables and filter focus; high contrast, reduced motion, 200% text, forced colors and JS-disabled fallback; no external requests, writes or JavaScript errors. Accessibility tree checked; actual screen reader not tested.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
