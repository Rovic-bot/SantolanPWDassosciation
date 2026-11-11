/* Synthetic loopback-only browser checks. No Django, database, or email service. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = path.resolve(__dirname, '..');
const posts = [], errors = [];
let ranking = 1, mode = 'success', base;
const html = (body, scripts = []) => `<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/static/css/action-feedback.css"><style>body{font:16px system-ui;margin:20px}button,input,textarea{padding:10px;margin:4px}main{max-width:700px}button{max-width:100%}</style>
<script src="/static/js/workspace-page.js"></script><script src="/static/js/action-feedback.js" defer></script>
${scripts.map(name => `<script src="/static/js/${name}.js" defer></script>`).join('')}</head><body><main id="main-content">${body}</main></body></html>`;
const token = '<input type="hidden" name="csrfmiddlewaretoken" value="synthetic-csrf">';
const native = html(`<form method="post" action="/native-email/" id="email">${token}
<label>Subject<input name="subject" required></label><button name="confirm" value="1">Send email</button>
<button disabled>Unavailable action</button></form><p id="delivery">No email sent.</p>`);
const review = (result = '') => html(`<section id="documents" data-document-review-saved></section>
<section id="decision"><h2 data-review-heading>Eligibility review</h2>${result}
<form id="eligibility-decision-form" data-applicant-review-form data-review-target="decision" action="/review/" method="post">${token}
<label for="notes">Remarks (optional)</label><textarea id="notes" name="notes"></textarea>
<p data-review-error hidden></p><button name="eligibility" value="eligible">Eligible</button>
<button name="eligibility" value="ineligible">Ineligible</button></form></section>`, ['admin-review']);
const ewaf = () => html(`<div data-ewaf-selection>
<form action="/ewaf/" data-selection-filters><input name="q"><select name="configuration"><option value="">All</option></select><button data-filter-submit>Filter programs</button></form>
<p data-selection-feedback role="status"></p><div class="selection-count"><strong data-selection-count>1</strong><span>program</span></div>
<div data-selection-results data-selected-id="1" data-result-count="1"><p data-selection-empty hidden>No programs</p><p data-analysis-empty hidden>No analysis</p>
<div class="selection-columns"><div data-program-row="1" data-search="Synthetic program" data-state="ready"><a href="?selected=1" data-select-program="1">Synthetic program</a></div>
<section class="selection-analysis"><article data-program-panel="1"><h2>Synthetic program</h2><div data-ranking-preview>Saved ranking ${ranking}</div>
<form data-generate-ranking data-program="1" action="/ewaf/run/" method="post">${token}<input name="action" type="hidden" value="GENERATE"><button>Generate EWAF Ranking</button></form>
</article></section></div></div></div>`, ['ewaf-selection']);
const receipt = html(`<div data-release-portfolio><a data-release-dialog href="/receipts/">View releases</a></div>
<dialog id="assistance-releases-dialog"><h2 id="release-dialog-title">Releases</h2><button data-release-close>Close</button>
<div data-release-dialog-status role="status"></div><div data-release-dialog-content></div></dialog>`, ['assistance-releases-dialog']);
const receipts = label => html(`<section data-release-table><h1>Receipts</h1><p role="status">${label}</p>
<form class="receipt-action-form" method="post" action="/receipts/email/retry/">${token}<input name="confirm" type="hidden" value="1"><button>Retry email</button></form></section>`);
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, base || 'http://localhost');
  const send = (body, status = 200, headers = {}) => {
    response.writeHead(status, {'content-type': 'text/html; charset=utf-8', ...headers}); response.end(body);
  };
  const interrupt = async () => {
    response.writeHead(200, {'content-type': 'text/html', 'content-length': '9000'});
    response.write('<html>');
    await new Promise(resolve => setTimeout(resolve, 20)); response.destroy();
  };
  if (url.pathname.startsWith('/static/')) {
    const file = path.resolve(root, '.' + url.pathname);
    if (!file.startsWith(path.join(root, 'static') + path.sep) || !fs.existsSync(file)) return send('', 404);
    return send(fs.readFileSync(file), 200, {'content-type': file.endsWith('.js') ? 'text/javascript' : 'text/css'});
  }
  if (request.method === 'POST') {
    let body = ''; for await (const chunk of request) body += chunk;
    posts.push({path: url.pathname, body});
    await new Promise(resolve => setTimeout(resolve, 800));
    if (url.pathname === '/native-email/') return send(html('<h1>Email not sent.</h1><p>The synthetic server rejected this request.</p>'), 400);
    if (url.pathname === '/review/') return mode === 'disconnect' ? interrupt() :
      send(review(mode === 'reject' ? '<p data-review-errors>Review could not be saved.</p>' : '<p id="delivery">Email sent.</p>'));
    if (url.pathname === '/receipts/email/retry/') return send(receipts(mode === 'reject' ? 'Email not sent.' : 'Email sent.'));
    if (url.pathname === '/ewaf/run/') {
      if (mode === 'disconnect') return interrupt();
      if (mode === 'reject') return send('<p class="alert-danger">Applicant information changed. Review readiness.</p>', 400);
      ranking++; return send('', 302, {location: '/ewaf/ranking/'});
    }
  }
  if (url.pathname === '/native/') return send(native);
  if (url.pathname === '/review/') return send(review());
  if (url.pathname === '/ewaf/') return send(ewaf());
  if (url.pathname === '/ewaf/ranking/') return send('<table class="ewaf-ranking-table"><tr><td>Synthetic saved run</td></tr></table>');
  if (url.pathname === '/releases/') return send(receipt);
  if (url.pathname === '/receipts/') return send(receipts('Email not sent.'));
  if (url.pathname === '/reports/') {
    if (url.searchParams.has('format')) {
      await new Promise(resolve => setTimeout(resolve, 600));
      return mode === 'reject' ? send('Access denied', 403) : send('category,count\nsynthetic,0', 200,
        {'content-type': 'text/csv', 'content-disposition': 'attachment; filename="synthetic-report.csv"'});
    }
    return send(html('<div class="member-report-exports"><a href="?format=csv">Export CSV</a></div>'));
  }
  return send('', 404);
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  let checks = 0;
  const pass = name => { checks++; console.log('PASS ' + name); };
  try {
    const page = await browser.newPage({acceptDownloads: true}); page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
    const visit = async target => { await page.goto(base + target); await page.waitForTimeout(50); };
    const count = target => posts.filter(post => post.path === target).length;

    await visit('/native/');
    await page.getByRole('button', {name: 'Send email', exact: true}).click();
    assert.equal(count('/native-email/'), 0); assert.equal(await page.locator('.is-processing').count(), 0);
    pass('native validation does not enter a pending state');
    await page.locator('[name=subject]').fill('Synthetic subject');
    const pendingEmail = await page.evaluate(() => {
      const form = document.querySelector('#email'); form.requestSubmit(form.querySelector('button'));
      const state = {spinner: !!document.querySelector('.action-spinner'), notice: document.querySelector('.action-progress')?.textContent,
        delivery: document.querySelector('#delivery').textContent};
      form.requestSubmit(); form.querySelector('button').click(); return state;
    });
    assert.equal(pendingEmail.spinner, true); assert.match(pendingEmail.notice, /Sending email/);
    assert.equal(pendingEmail.delivery, 'No email sent.');
    await page.getByRole('heading', {name: 'Email not sent.'}).waitFor();
    assert.equal(count('/native-email/'), 1);
    const sent = new URLSearchParams(posts.at(-1).body);
    assert.equal(sent.get('confirm'), '1'); assert.equal(sent.get('subject'), 'Synthetic subject');
    assert.equal(sent.get('csrfmiddlewaretoken'), 'synthetic-csrf');
    pass('native email shows pending immediately, keeps named actions/CSRF, blocks duplicates, then displays server failure');

    await visit('/native/');
    await page.evaluate(() => window.addEventListener('submit', event => event.preventDefault(), {once: true}));
    await page.locator('[name=subject]').fill('Synthetic cached form');
    await page.getByRole('button', {name: 'Send email', exact: true}).click();
    await page.locator('.is-processing').waitFor();
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true})));
    assert.equal(await page.locator('.is-processing').count(), 0);
    assert.equal(await page.getByRole('button', {name: 'Send email', exact: true}).isEnabled(), true);
    assert.equal(await page.getByRole('button', {name: 'Unavailable action'}).isDisabled(), true);
    pass('cached-page restoration restores labels and preserves already-disabled controls');

    await visit('/review/');
    await page.getByRole('button', {name: 'Ineligible', exact: true}).click();
    assert.equal(count('/review/'), 0); assert.equal(await page.locator('.is-processing').count(), 0);
    await page.getByRole('button', {name: 'Eligible', exact: true}).click();
    await page.locator('.action-spinner').waitFor();
    assert.match(await page.locator('.action-progress').innerText(), /Saving decision and sending email/);
    await page.evaluate(() => document.querySelector('form').requestSubmit(document.querySelector('button[value=ineligible]')));
    await page.locator('#delivery').waitFor(); assert.equal(count('/review/'), 1);
    assert.match(posts.at(-1).body, /name="eligibility"\r\n\r\neligible/);
    assert.equal(await page.locator('.is-processing').count(), 0);
    pass('actual eligibility controller validates remarks, preserves decision, prevents duplicates, and waits for confirmed HTML');
    mode = 'disconnect';
    await page.getByRole('button', {name: 'Eligible', exact: true}).click();
    await page.locator('[data-review-error]:not([hidden])').waitFor();
    assert.equal(await page.locator('.is-processing').count(), 0);
    assert.equal(await page.getByRole('button', {name: 'Eligible', exact: true}).isEnabled(), true);
    assert.equal(count('/review/'), 2);
    pass('actual eligibility controller restores controls on network failure without automatically resending');

    mode = 'success'; await visit('/ewaf/');
    await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).click();
    await page.locator('.action-spinner').waitFor();
    assert.equal(await page.locator('[data-ranking-preview]').innerText(), 'Saved ranking 1');
    await page.evaluate(() => document.querySelector('[data-generate-ranking]').requestSubmit());
    await page.waitForFunction(() => document.querySelector('[data-ranking-preview]')?.textContent === 'Saved ranking 2');
    assert.equal(count('/ewaf/run/'), 1); assert.equal(await page.locator('.is-processing').count(), 0);
    pass('actual EWAF controller retains saved ranking until the POST redirect confirms its replacement');
    mode = 'reject'; await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('[data-selection-feedback]').textContent.includes('Applicant information changed'));
    assert.equal(await page.locator('[data-ranking-preview]').innerText(), 'Saved ranking 2');
    assert.equal(await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).isEnabled(), true);
    pass('EWAF server rejection retains the previous ranking and restores a usable form');
    mode = 'disconnect'; await page.getByRole('button', {name: 'Generate EWAF Ranking', exact: true}).click();
    await page.getByRole('link', {name: 'Reload ranking status'}).waitFor();
    assert.equal(await page.locator('.action-spinner').count(), 0);
    assert.equal(count('/ewaf/run/'), 3);
    pass('uncertain EWAF write stops its spinner and offers a read-only status reload, without replaying the calculation');

    mode = 'reject'; await visit('/releases/');
    await page.getByRole('link', {name: 'View releases'}).click();
    await page.getByRole('button', {name: 'Retry email', exact: true}).click();
    await page.locator('.action-spinner').waitFor();
    assert.match(await page.locator('[data-release-dialog-status]').innerText(), /Sending beneficiary email/);
    await page.evaluate(() => document.querySelector('dialog form').requestSubmit());
    await page.getByRole('button', {name: 'Retry email', exact: true}).waitFor();
    assert.equal(count('/receipts/email/retry/'), 1);
    assert.equal(await page.locator('.action-spinner').count(), 0);
    pass('dynamically loaded receipt email retry has immediate pending feedback and a working retry after server failure');

    mode = 'success'; await visit('/reports/');
    const downloaded = page.waitForEvent('download'); await page.getByRole('link', {name: 'Export CSV'}).click();
    await page.locator('.action-spinner').waitFor();
    const download = await downloaded; assert.equal(download.suggestedFilename(), 'synthetic-report.csv');
    await page.getByRole('link', {name: 'Export CSV'}).waitFor();
    assert.equal(await page.locator('.action-spinner').count(), 0);
    mode = 'reject'; await page.getByRole('link', {name: 'Export CSV'}).click();
    await page.waitForFunction(() => document.querySelector('[data-download-feedback]')?.textContent.includes('could not'));
    assert.equal(await page.getByRole('link', {name: 'Export CSV'}).getAttribute('aria-disabled'), null);
    pass('report exports track file generation, preserve filenames, and recover from denied downloads');

    await visit('/native/');
    await page.evaluate(() => { document.querySelector('form').addEventListener('submit', event => event.preventDefault()); });
    await page.locator('[name=subject]').fill('Cancelled');
    await page.getByRole('button', {name: 'Send email', exact: true}).click();
    assert.equal(await page.locator('.is-processing').count(), 0);
    pass('cancelled submissions do not lock controls');
    await page.evaluate(() => {
      const form = document.querySelector('form');
      window.firstPending = ActionFeedback.start(form);
      window.secondPending = ActionFeedback.start(form);
      window.firstPending();
    });
    assert.equal(await page.locator('.action-spinner').count(), 1);
    await page.evaluate(() => window.secondPending());
    assert.equal(await page.locator('.action-spinner').count(), 0);
    pass('overlapping previews keep feedback active until every request finishes');
    await page.clock.install();
    await page.evaluate(() => { window.finishPending = ActionFeedback.start(document.querySelector('form')); });
    await page.clock.fastForward(16000);
    assert.match(await page.locator('.action-progress').innerText(), /taking longer.*still pending/);
    assert.equal(await page.locator('.action-spinner').count(), 1);
    await page.evaluate(() => window.finishPending());
    await page.clock.resume();
    pass('slow requests remain pending and never manufacture a success or retry');
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.evaluate(() => { window.finishPending = ActionFeedback.start(document.querySelector('form')); });
    assert.equal(await page.locator('.action-spinner').evaluate(node => getComputedStyle(node).animationName), 'none');
    await page.emulateMedia({reducedMotion: 'no-preference'});
    await page.evaluate(() => { document.documentElement.dataset.motion = 'reduce'; });
    assert.equal(await page.locator('.action-spinner').evaluate(node => getComputedStyle(node).animationName), 'none');
    for (const width of [390, 320]) {
      await page.setViewportSize({width, height: 800});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    }
    await page.evaluate(() => WorkspacePage.replace());
    assert.equal(await page.locator('.is-processing, .action-progress').count(), 0);
    assert.equal(await page.evaluate(() => typeof window.ActionFeedback), 'undefined');
    pass('mobile layout, system/site reduced motion, and workspace disposal retain usable controls');
    assert.deepEqual(errors, []);
    console.log(`${checks} browser checks passed; no actual records, email delivery, or EWAF calculations performed.`);
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; server.close(); });
