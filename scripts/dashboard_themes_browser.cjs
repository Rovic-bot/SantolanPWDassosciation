/* Read-only browser checks using HTML emitted by analytics' isolated fixture test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = process.cwd();
const fixtures = path.join(root, '.local/dashboard-charts-20261029');
const output = path.resolve(process.env.DASHBOARD_QA_OUTPUT || path.join(root, 'docs/dashboard-stability-2026-11-01'));
const base = process.env.DASHBOARD_BASE_URL || 'http://127.0.0.1:8013';
const expected = JSON.parse(fs.readFileSync(path.join(fixtures, 'expected.json'), 'utf8'));
fs.mkdirSync(output, {recursive:true});
// A presentation-only fixture exercises ten rows and coincident scatter points.
// It never touches the application database.
function denseFixture() {
  let html = fs.readFileSync(path.join(fixtures,'after.html'),'utf8');
  const replaceCard = (id, headline, summary, rows) => {
    const pattern = new RegExp(`(<section[^>]+data-chart-id="${id}">)([\\s\\S]*?)(</section>)`);
    html = html.replace(pattern, (_, start, card, end) => start + card
      .replace(/(<p class="overview-headline">)[\s\S]*?(<\/p>)/, `$1${headline}$2`)
      .replace(/(<p class="overview-summary"[^>]*>)[\s\S]*?(<\/p>)/, `$1${summary}$2`)
      .replace(/<tbody>[\s\S]*?<\/tbody>/, '<tbody>'+rows.map(row=>'<tr>'+row.map((cell,i)=>`<${i?'td':'th'}>${cell}</${i?'td':'th'}>`).join('')+'</tr>').join('')+'</tbody>') + end);
  };
  const replacePayload = (id, update) => {
    const pattern = new RegExp(`(<script id="${id}" type="application/json">)([\\s\\S]*?)(</script>)`);
    html = html.replace(pattern, (_, start, json, end) => start + JSON.stringify(update(JSON.parse(json))) + end);
  };
  replacePayload('eligibility-stack', data => ({...data,
    labels:Array.from({length:10},(_,i)=>`${i+1}. Synthetic program ${i+1}`),
    series:data.series.map((series,j)=>({...series,values:Array(10).fill(j===0?12:0)})), total:120}));
  replacePayload('capacity-scatter', data => ({...data,total:10,
    points:[11,9,5,2,12,12,12,12,12,1].map((y,i)=>({label:String(i+1),x:i===9?10:12,y}))}));
  replaceCard('eligibility-stack','120 applications','120 applications across 10 synthetic programs.',
    Array.from({length:10},(_,i)=>[`${i+1}. Synthetic program ${i+1}`,12,0,0,0,0,0,12]));
  replaceCard('capacity-scatter','10 programs','10 synthetic programs with known capacity.',
    [11,9,5,2,12,12,12,12,12,1].map((y,i)=>[`${i+1}. Synthetic program ${i+1}`,i===9?10:12,y,'01 Oct 2026, 00:00','28 Oct 2026, 00:00']));
  return html;
}

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], blocked = [];
  async function context(options = {}) {
    const ctx = await browser.newContext({viewport:{width:1440,height:1100}, colorScheme:'dark', ...options});
    await ctx.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== base || request.method() !== 'GET') {
        blocked.push(request.method() + ' ' + url.pathname); return route.abort();
      }
      if (url.pathname === '/dashboard/') {
        const name = url.searchParams.get('fixture') || (url.searchParams.has('period') ? 'filtered' : 'after');
        return route.fulfill({contentType:'text/html; charset=utf-8', body:name==='dense'?denseFixture():fs.readFileSync(path.join(fixtures,name+'.html'))});
      }
      await route.continue();
    });
    return ctx;
  }
  const overflow = page => page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  async function checkScatterStability(page) {
    const scatter=page.locator('[data-chart="capacity-scatter"]');
    await scatter.scrollIntoViewIfNeeded();
    await page.evaluate(()=>{
      const host=document.querySelector('[data-chart="capacity-scatter"]');
      window.scatterRepaints=0;
      window.scatterObserver=new MutationObserver(()=>window.scatterRepaints++);
      window.scatterObserver.observe(host,{childList:true});
    });
    const measure=()=>scatter.evaluate(host=>[host.clientWidth,host.clientHeight,host.scrollWidth,host.scrollHeight,host.querySelector('svg').getBoundingClientRect().width]);
    const baseline=await measure();
    assert.equal(baseline[0],baseline[2],'Unnecessary horizontal chart scrollbar');
    assert.equal(baseline[1],baseline[3],'Unnecessary vertical chart scrollbar');
    for(const point of await scatter.locator('[data-scatter-point]').all()) {
      await point.hover(); await point.focus();
      const samples=await scatter.evaluate(host=>new Promise(resolve=>{
        const sizes=[];
        function sample(){sizes.push([host.clientWidth,host.clientHeight,host.scrollWidth,host.scrollHeight,host.querySelector('svg').getBoundingClientRect().width]);if(sizes.length<8)requestAnimationFrame(sample);else resolve(sizes);}
        requestAnimationFrame(sample);
      }));
      assert(samples.every(size=>JSON.stringify(size)===JSON.stringify(baseline)),'Tooltip changed chart dimensions');
    }
    assert.equal(await page.evaluate(()=>window.scatterRepaints),0,'Hover/focus redrew the scatter plot');
    await page.evaluate(()=>window.scatterObserver.disconnect());
  }
  async function checkLegendContrast(page) {
    const minimum = await page.locator('.overview-key').evaluateAll(nodes => {
      const luminance = color => {const c=color.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;});return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
      return Math.min(...nodes.map(node=>{const s=getComputedStyle(node),a=luminance(s.color),b=luminance(s.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);}));
    });
    assert(minimum>=4.5,'Legend text contrast: '+minimum);
  }
  try {
    const systemContext = await context({colorScheme:'light'});
    const systemPage = await systemContext.newPage();
    await systemPage.goto(base+'/dashboard/?fixture=after');
    assert.equal(await systemPage.locator('html').getAttribute('data-dashboard-theme'),'light');
    await checkLegendContrast(systemPage);
    await systemPage.emulateMedia({colorScheme:'dark'});
    await systemPage.waitForFunction(()=>document.documentElement.dataset.dashboardTheme==='dark');
    await checkLegendContrast(systemPage);
    await systemPage.getByRole('button',{name:'Switch to light mode',exact:true}).click();
    await systemPage.emulateMedia({colorScheme:'light'});
    await systemPage.emulateMedia({colorScheme:'dark'});
    assert.equal(await systemPage.locator('html').getAttribute('data-dashboard-theme'),'light');
    await systemPage.reload();
    assert.equal(await systemPage.locator('html').getAttribute('data-dashboard-theme'),'light');
    assert.equal(await systemPage.locator('.dashboard-public-link').getAttribute('href'),'/');
    await systemContext.close();
    const blockedStorage = await context();
    await blockedStorage.addInitScript(() => Object.defineProperty(window,'localStorage', {get() {throw new DOMException('Storage blocked','SecurityError');}}));
    const storagePage = await blockedStorage.newPage();
    await storagePage.goto(base+'/dashboard/?fixture=after');
    await storagePage.getByRole('button',{name:'Switch to light mode',exact:true}).click();
    assert.equal(await storagePage.locator('html').getAttribute('data-dashboard-theme'),'light');
    await blockedStorage.close();
    const ctx = await context(); const page = await ctx.newPage();
    page.on('pageerror', error => errors.push(error.message));
    for (const width of [1440, 1024, 768, 390, 320]) {
      await page.setViewportSize({width,height:1100});
      await page.goto(base + '/dashboard/?fixture=after');
      await page.waitForLoadState('networkidle');
      assert.equal(await page.locator('.overview-metric').count(), 8);
      assert.equal(await page.locator('.overview-metric:visible').count(), 4);
      assert.equal(await page.locator('.overview-data[open]').count(), 0);
      assert.equal(await page.locator('[data-open-chart-data]:visible').count(),12);
      assert.equal(await page.locator('.overview-header,.overview-intro').count(),0);
      assert.equal(await page.locator('h1').textContent(),'Dashboard');
      const filterGap=await page.locator('.overview-filters').evaluate(form=>form.getBoundingClientRect().top-form.closest('.analytics-overview').getBoundingClientRect().top);
      assert(filterGap<=33,'Removed hero left a large blank gap');
      assert.equal(await page.locator('[data-custom-date]:visible').count(), 0);
      assert.equal(await page.locator('.overview-section').count(), 12);
      assert.equal(await page.locator('.overview-visual svg').count(), 11);
      assert.equal(await page.locator('.overview-heatmap').count(), 1);
      assert.equal(await page.locator('[data-chart-fallback]:visible').count(), 0);
      assert(!await overflow(page), 'Page overflow at '+width);
      if (width >= 992) {
        const cards = await page.locator('.overview-section').evaluateAll(cards => cards.map(card => {
          const rect = card.getBoundingClientRect(), plot = card.querySelector('.overview-visual')?.getBoundingClientRect();
          return {id:card.dataset.chartId, top:rect.top, height:rect.height, plotTop:plot?.top};
        }));
        for (const [left,right] of [[0,1],[2,3],[4,5],[6,7],[9,10]]) {
          assert(Math.abs(cards[left].top - cards[right].top) < 1, 'Card top alignment');
          assert(Math.abs(cards[left].height - cards[right].height) < 1, 'Card bottom alignment');
          // The member donut has a central total instead of a separate headline.
          if(left!==0)assert(Math.abs(cards[left].plotTop - cards[right].plotTop) < 1, 'Chart plot alignment');
        }
      }
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
    await page.setViewportSize({width:1440,height:1100});
    await page.goto(base+'/dashboard/?fixture=after');
    await page.getByRole('button',{name:'Switch to light mode',exact:true}).click();
    assert.equal(await page.locator('html').getAttribute('data-dashboard-theme'),'light');
    await page.screenshot({path:path.join(output,'light-desktop.png'),fullPage:true});
    await page.reload();
    assert.equal(await page.locator('html').getAttribute('data-dashboard-theme'),'light');
    await page.setViewportSize({width:390,height:1100});
    assert(!await overflow(page),'Light mobile overflow');
    await page.screenshot({path:path.join(output,'light-mobile.png'),fullPage:true});
    await page.getByRole('button',{name:'Switch to dark mode',exact:true}).click();
    const dialog = page.locator('#overview-data-dialog');
    for (const trigger of await page.locator('[data-open-chart-data]').all()) {
      const before = await trigger.locator('..').evaluate(node=>node.getBoundingClientRect().height);
      await trigger.focus(); await page.keyboard.press('Enter');
      assert(await dialog.evaluate(node=>node.matches(':modal')));
      const id=await dialog.getAttribute('data-chart-id'), chart=expected.visualizations.find(chart=>chart.id===id);
      const rows=await dialog.locator('tbody tr').evaluateAll(rows=>rows.map(row=>[...row.querySelectorAll('th,td')].map(cell=>cell.textContent.trim())));
      assert.deepEqual(rows,chart.rows,'Modal table: '+id);
      assert(await dialog.evaluate(node=>node.contains(document.activeElement)));
      for (let i=0;i<5;i++) {await page.keyboard.press('Tab');assert(await dialog.evaluate(node=>node.contains(document.activeElement)));}
      for (let i=0;i<3;i++) {await page.keyboard.press('Shift+Tab');assert(await dialog.evaluate(node=>node.contains(document.activeElement)));}
      assert(!await overflow(page),'Modal caused page overflow');
      await page.keyboard.press('Escape'); await dialog.waitFor({state:'hidden'});
      assert(await trigger.evaluate(node=>document.activeElement===node),'Focus not restored');
      assert.equal(await trigger.locator('..').evaluate(node=>node.getBoundingClientRect().height),before);
    }
    for (const width of [1920,1440,390,320]) {
      await page.setViewportSize({width,height:1100});
      await page.goto(base+'/dashboard/?fixture=dense');
      await page.waitForLoadState('networkidle');
      const eligibility=page.locator('[data-chart="eligibility-stack"]');
      const visibleRows=await eligibility.evaluate(host=>{
        const frame=host.getBoundingClientRect();
        return [...host.querySelectorAll('[data-program-row]')].filter(row=>{
          const r=row.getBoundingClientRect();return r.top>=frame.top && r.bottom<=frame.bottom;
        }).map(row=>Number(row.dataset.programRow));
      });
      assert.deepEqual(visibleRows,[1,2,3,4,5]);
      assert.equal(await eligibility.getAttribute('tabindex'),'0');
      await eligibility.focus(); await page.keyboard.press('End');
      await page.waitForTimeout(150);
      assert(await eligibility.evaluate(node=>node.scrollTop>0));
      const scatter=page.locator('[data-chart="capacity-scatter"]');
      assert.equal(await scatter.locator('[data-scatter-point]').count(),6);
      const combined=scatter.getByRole('img',{name:/Programs 5, 6, 7, 8, 9/});
      await combined.focus();
      const tooltip=scatter.locator('..').getByRole('tooltip');
      assert(await tooltip.isVisible());assert.match(await tooltip.innerText(),/12 slots · 12 applications/);
      assert(await tooltip.evaluate(node=>{const r=node.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}));
      await page.keyboard.press('Escape');assert(!await tooltip.isVisible());
      await combined.hover();assert(await tooltip.isVisible());
      await checkScatterStability(page);
      if(width===1440) {
        await page.evaluate(()=>document.documentElement.style.fontSize='110%');
        await page.waitForTimeout(150);
        await checkScatterStability(page);
        await page.evaluate(()=>document.documentElement.style.fontSize='');
        await page.waitForTimeout(150);
      }
      if(width===1440) {
        const ring=page.locator('[data-chart="program-pie"] circle[data-value]').first();
        assert(Number(await ring.getAttribute('r'))>=70,'Status rings remain too small');
        await page.locator('[data-chart-id="program-pie"]').screenshot({path:path.join(output,'status-rings.png')});
        await scatter.scrollIntoViewIfNeeded();
        await page.locator('[data-visualization="capacity-scatter"] [data-open-chart-data]').focus();
        await combined.focus(); assert(await tooltip.isVisible());
        await scatter.screenshot({path:path.join(output,'scatter-tooltip.png')});
        await eligibility.evaluate(node=>{node.scrollTop=0;});
        await page.locator('[data-chart-id="eligibility-stack"]').screenshot({path:path.join(output,'eligibility-five-rows.png')});
      }
      await page.locator('[data-visualization="eligibility-stack"] [data-open-chart-data]').click();
      assert(await dialog.isVisible());
      await dialog.screenshot({path:path.join(output,`data-dialog-${width}.png`)});
      await page.getByRole('button',{name:'Close data',exact:true}).click();
      await dialog.waitFor({state:'hidden'});
      await page.getByRole('button',{name:'Switch to light mode',exact:true}).click();
      const dataTrigger=page.locator('[data-visualization="eligibility-stack"] [data-open-chart-data]');
      await dataTrigger.click();
      assert.equal(await dialog.evaluate(node=>getComputedStyle(node).backgroundColor),'rgb(244, 242, 236)');
      await dialog.screenshot({path:path.join(output,`data-dialog-light-${width}.png`)});
      if(width===1440) await page.mouse.click(3,3);
      else await page.getByRole('button',{name:'Close data',exact:true}).click();
      await dialog.waitFor({state:'hidden'});
      assert(await dataTrigger.evaluate(node=>document.activeElement===node));
      await page.getByRole('button',{name:'Switch to dark mode',exact:true}).click();
    }
    await page.setViewportSize({width:1440,height:1100});
    await page.goto(base+'/dashboard/?fixture=after');
    await page.locator('.overview-more > summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('.overview-metric:visible').count(),8);
    await page.keyboard.press('Enter');
    await page.getByLabel('Activity period',{exact:true}).selectOption('custom');
    assert.equal(await page.locator('[data-custom-date]:visible').count(),2);
    await page.getByLabel('Start date',{exact:true}).fill('2026-10-29');
    await page.getByLabel('End date',{exact:true}).fill('2026-10-29');
    await page.getByLabel('End date',{exact:true}).press('Tab');
    await page.waitForURL(/period=custom/);
    assert.equal(await page.evaluate(()=>document.activeElement.id),'id_end');
    assert.equal(await page.locator('.overview-visual svg').count(),11);
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
    const fill = await page.locator('[data-chart="disability-bar"] [data-member-segment]').first().evaluate(el=>getComputedStyle(el)[el.tagName==='circle'?'stroke':'fill']);
    assert.equal(fill,'rgb(47, 98, 91)');
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
    assert.equal(await page.locator('.overview-visual svg').count(),11);
    const font = await page.locator('[data-chart="disability-bar"] text').first().getAttribute('font-size');
    assert(Number(font)>=32,'SVG labels did not enlarge');
    const scrollable = page.locator('.overview-visual[tabindex="0"]').first();
    await scrollable.focus(); await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(150);
    assert(await scrollable.evaluate(node=>node.scrollLeft>0),'Enlarged chart cannot scroll by keyboard');
    await page.screenshot({path:path.join(output,'text-200-percent-320.png'),fullPage:true});
    await page.locator('[data-visualization="eligibility-stack"] [data-open-chart-data]').click();
    assert(await dialog.isVisible());assert(!await overflow(page));
    await dialog.screenshot({path:path.join(output,'data-dialog-200-percent.png')});
    await page.getByRole('button',{name:'Close data',exact:true}).click();
    await page.emulateMedia({forcedColors:'active',reducedMotion:'reduce'});
    const session = await ctx.newCDPSession(page);
    const tree = await session.send('Accessibility.getFullAXTree');
    assert(tree.nodes.some(node=>node.role?.value==='image' && node.name?.value==='Cumulative new memberships'));
    assert(tree.nodes.some(node=>node.role?.value==='table' && node.name?.value.includes('Scheduled events')));
    const noJS = await context({javaScriptEnabled:false,viewport:{width:390,height:1100}});
    const fallback = await noJS.newPage();await fallback.goto(base+'/dashboard/?fixture=after');
    assert.equal(await fallback.locator('.overview-data-table:visible').count(),12);
    assert(!await overflow(fallback));
    await fallback.screenshot({path:path.join(output,'no-javascript.png'),fullPage:true});
    assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
    console.log('PASS: twelve charts and modal tables match synthetic aggregates; five-row scrolling; larger status rings; clustered scatter tooltips; modal focus cycle, Escape/Close/backdrop and focus return; dark/light at 1440/1024/768/390/320; high contrast, reduced motion, 200% text, forced colors and JS-disabled fallback; no external requests, writes or JavaScript errors. Accessibility tree checked; actual screen reader not tested.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
