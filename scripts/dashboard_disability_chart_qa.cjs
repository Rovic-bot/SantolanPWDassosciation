/* Read-only chart checks using HTML produced by the isolated analytics test. */
const assert = require('node:assert/strict'), fs = require('node:fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = process.env.DASHBOARD_BASE_URL || 'http://127.0.0.1:8013';
const output = process.env.DASHBOARD_QA_OUTPUT || 'docs/dashboard-disability-donut-2026-11-08';
const fixture = fs.readFileSync('.local/dashboard-charts-20261029/after.html', 'utf8');
assert(fixture.includes('data-chart-kind="member-donut"'), 'First run analytics.tests.OverviewTests.test_render_privacy_tables_and_capture_synthetic_evidence.');
const samples = {
  all: { labels: ['Visual Disability', 'Learning Disability', 'Cancer (RA 11215)', 'Intellectual Disability', 'Physical Disability (Orthopedic)', 'Rare Disease (RA 10747)', 'Classification not recorded'], values: [10, 3, 1, 1, 1, 1, 2], members: 19 },
  overlap: { labels: ['Visual Disability', 'Deaf or Hard of Hearing', 'Classification not recorded'], values: [2, 1, 1], members: 3 },
  single: { labels: ['Visual Disability'], values: [3], members: 3 },
  small: { labels: ['Visual Disability', 'Learning Disability', 'Cancer (RA 11215)'], values: [98, 1, 1], members: 100 },
  catalog: { labels: ['Cancer (RA 11215)', 'Deaf or Hard of Hearing', 'Intellectual Disability', 'Learning Disability', 'Mental Disability', 'Physical Disability (Orthopedic)', 'Psychosocial Disability', 'Rare Disease (RA 10747)', 'Speech and Language Impairment', 'Visual Disability', 'Classification not recorded'], values: Array(11).fill(1), members: 11 },
  empty: { labels: [], values: [], members: 0 }
};
function html(sample) {
  const data = { kind: 'member-donut', labels: sample.labels, series: [{name: 'Count', values: sample.values}], total: sample.values.reduce((a, b) => a + b, 0), denominator: sample.members };
  return fixture.replace(/(<script id="disability-bar" type="application\/json">)[\s\S]*?(<\/script>)/, (_, start, end) => start + JSON.stringify(data) + end)
    .replace(/(<section[^>]+data-chart-id="disability-bar">)([\s\S]*?)(<\/section>)/, (_, start, card, end) => start + card
      .replace(/(<p class="overview-headline">)[\s\S]*?(<\/p>)/, `$1${sample.members}$2`)
      .replace(/(<p class="overview-summary"[^>]*>)[\s\S]*?(<\/p>)/, `$1${sample.members} current official members; archived records excluded.$2`)
      .replace(/<tbody>[\s\S]*?<\/tbody>/, '<tbody>' + sample.labels.map((label, i) => `<tr><th>${label}</th><td>${sample.values[i]}</td><td>${(sample.members ? sample.values[i] / sample.members * 100 : 0).toFixed(1)}%</td></tr>`).join('') + '</tbody>') + end);
}
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    fs.mkdirSync(output, {recursive: true});
    const errors = [], blocked = [], checks = [];
    const context = await browser.newContext();
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== base || request.method() !== 'GET') { blocked.push(request.method() + ' ' + url.pathname); return route.abort(); }
      if (url.pathname === '/dashboard/') return route.fulfill({contentType: 'text/html', body: html(samples[url.searchParams.get('sample') || 'all'])});
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    const host = page.locator('[data-chart="disability-bar"]');
    async function verify(sample) {
      await page.waitForSelector('[data-chart="disability-bar"] svg');
      const segments = await host.locator('[data-member-segment]').evaluateAll(nodes => nodes.map(node => ({
        count: Number(node.dataset.value), fraction: Number(node.dataset.fraction),
        color: node.tagName === 'circle' ? getComputedStyle(node).stroke : getComputedStyle(node).fill,
        title: node.querySelector('title').textContent
      })));
      assert.deepEqual(segments.map(segment => segment.count), sample.values);
      const total = sample.values.reduce((a,b)=>a+b,0);
      const shares = await host.locator('[data-member-share]').allTextContents();
      const colors = await host.locator('[data-member-key]').evaluateAll(nodes=>nodes.map(node=>getComputedStyle(node).fill));
      segments.forEach((segment, i) => {
        assert(Math.abs(segment.fraction - sample.values[i] / total) < 1e-9, 'Segments partition classification counts, including overlapping classifications.');
        assert(segment.fraction > 0 && segment.color !== 'none');
        assert.equal(segment.color, colors[i]);
        assert(segment.title.startsWith(sample.labels[i] + ':'));
        assert.equal(shares[i],`${sample.values[i].toLocaleString('en-US')} (${(sample.values[i] / sample.members * 100).toFixed(1)}%)`, 'Legend percentages still use distinct members.');
      });
      assert.equal(await host.locator('[data-member-total]').textContent(), sample.members.toLocaleString('en-US'));
      if (segments.length) assert(Math.abs(segments.reduce((sum,segment)=>sum+segment.fraction,0)-1) < 1e-9);
      assert(await host.evaluate(el => el.scrollHeight <= el.clientHeight + 1), 'All types must fit without vertical chart scrolling.');
      assert(await host.evaluate(el => el.scrollWidth <= el.clientWidth + 1), 'Chart fits without horizontal scrolling.');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const clipped = await host.locator('svg').evaluate(svg => {
        const bounds = svg.getBoundingClientRect();
        return [...svg.querySelectorAll('text')].filter(text => { const r = text.getBoundingClientRect(); return r.left < bounds.left - 1 || r.right > bounds.right + 1 || r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1; }).map(el => el.textContent);
      });
      assert.deepEqual(clipped, []);
      assert(!(await host.innerHTML()).match(/NaN|Infinity/));
      return segments;
    }
    for (const theme of ['dark', 'light']) {
      for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({width, height: 1000});
        await page.goto(base + '/dashboard/');
        await page.evaluate(theme => { document.documentElement.dataset.dashboardTheme = theme; }, theme);
        const segments = await verify(samples.all);
        assert.equal(new Set(segments.map(segment => segment.color)).size, samples.all.labels.length);
        if ([1440, 390].includes(width)) await page.locator('[data-chart-id="disability-bar"]').screenshot({path: `${output}/${theme}-${width}.png`});
        checks.push({theme, width, segments: segments.length});
      }
    }
    for (const key of ['overlap', 'single', 'empty', 'small', 'catalog']) {
      await page.goto(base + '/dashboard/?sample=' + key);
      const segments = await verify(samples[key]);
      assert.equal(new Set(segments.map(segment=>segment.color)).size, segments.length);
    }
    // Actual test-rendered tables retain the source count and member denominator.
    await page.route('**/dashboard/?sample=table', route => route.fulfill({contentType: 'text/html', body: fixture}));
    await page.goto(base + '/dashboard/?sample=table');
    await page.locator('[data-visualization="disability-bar"] [data-open-chart-data]').click();
    const dialog = page.locator('#overview-data-dialog');
    await dialog.waitFor({state: 'visible'});
    const rows = await dialog.locator('tbody tr').allTextContents();
    assert(rows.some(row => /Visual Disability/.test(row) && /66.7%/.test(row)));
    assert(rows.some(row => /Classification not recorded/.test(row) && /33.3%/.test(row)));
    await page.keyboard.press('Escape');
    await page.goto(base + '/dashboard/');
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; document.documentElement.dataset.contrast = 'true'; });
    await page.waitForFunction(() => document.querySelector('[data-chart="disability-bar"] svg')?.getAttribute('height') > 800);
    await verify(samples.all);
    await page.emulateMedia({forcedColors: 'active', reducedMotion: 'reduce'});
    await verify(samples.all);
    const plain = await browser.newPage({javaScriptEnabled: false});
    await plain.route('**/dashboard/', route => route.fulfill({contentType: 'text/html', body: fixture}));
    await plain.goto(base + '/dashboard/');
    assert(await plain.locator('[data-visualization="disability-bar"] .overview-data-table').isVisible());
    await plain.close();
    assert.deepEqual(errors, []); assert.deepEqual(blocked, []);
    fs.writeFileSync(`${output}/results.json`, JSON.stringify({checks, overlap: true, single: true, empty: true, tinySegments: true, fullCatalog: true, dataTable: true, largeText: true, forcedColors: true, noJavaScript: true, errors}, null, 2));
    console.log('Disability doughnut passed: every category rendered, accurate ring proportions and member-based shares, responsive themes and accessible data table.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
