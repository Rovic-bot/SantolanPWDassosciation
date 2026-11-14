// Real Chrome, actual Django partials/assets, synthetic attachments only; no database or authentication.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = path.resolve(__dirname, '..');
const output = path.resolve(process.env.QA_OUTPUT || path.join(root, '.local/document-preview-qa'));
const python = process.env.QA_PYTHON || 'python';
const rendered = spawnSync(python, ['-'], {cwd: root, encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8'}, input: String.raw`
import base64, io, json, sys, types
from pathlib import Path
from types import SimpleNamespace as S
from django.conf import settings
from django.urls import path, include
urls = types.ModuleType('qa_urls')
urls.urlpatterns = [path('programs/', include(([
 path('<int:program>/<int:application>/document/<int:document>', lambda r: None, name='document'),
 path('<int:application>/photo/<int:photo>', lambda r: None, name='photo'),
], 'programs'))), path('members/', include(([
 path('<int:member>/document/<int:document>', lambda r: None, name='document'),
], 'members')))]
sys.modules['qa_urls'] = urls
settings.configure(USE_I18N=False, SECRET_KEY='synthetic-template-only', ROOT_URLCONF='qa_urls')
import django
django.setup()
from django.template import Context, Engine
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
engine = Engine(dirs=[str(Path.cwd() / 'templates')])
documents = [S(pk=1, label='Synthetic PDF', source_document_id=None), S(pk=2, label='Synthetic PNG', source_document_id=None)]
data = dict(application=S(pk=1, program_id=1, member_id=1, current_photo_id=1, member=S(full_name='Synthetic Applicant')),
 can_view_photo=True, can_view_program_documents=True, program=S(name='Synthetic program'),
 program_requirement_rows=[S(kind='document', label=d.label, document=d) for d in documents],
 review_documents=[S(document=d, status='Submitted') for d in documents], membership_documents=[])
result = {name: engine.get_template('programs/' + name + '.html').render(Context(data))
 for name in ['submission_review', 'applicant_documents', 'document_preview_dialog']}
data['document'] = S(pk=3, label='Synthetic member document', review_status='Verified')
result['member_document_card'] = engine.get_template('programs/member_document_card.html').render(Context(data))
image = Image.new('RGB', (1000, 700), '#e3f5f1')
draw = ImageDraw.Draw(image)
draw.rectangle((55, 55, 945, 645), outline='#146e62', width=8)
draw.text((90, 120), 'SYNTHETIC DOCUMENT PREVIEW - NO PERSONAL INFORMATION', fill='#164d46', font_size=25)
draw.text((90, 180), 'Image attachment stays above the applicant review.', fill='#164d46', font_size=23)
for name, fmt in [('png', 'PNG'), ('jpeg', 'JPEG')]:
 stream = io.BytesIO(); image.save(stream, format=fmt); result[name] = base64.b64encode(stream.getvalue()).decode()
stream = io.BytesIO(); pdf = canvas.Canvas(stream, pagesize=(612, 792)); pdf.setTitle('Synthetic document preview')
pdf.setFont('Helvetica-Bold', 20); pdf.drawString(50, 710, 'SYNTHETIC DOCUMENT PREVIEW')
pdf.setFont('Helvetica', 13); pdf.drawString(50, 670, 'PDF attachment stays above the applicant review.')
pdf.drawString(50, 645, 'No personal information. Browser regression fixture only.')
pdf.rect(50, 480, 510, 130); pdf.save(); result['pdf'] = base64.b64encode(stream.getvalue()).decode()
print(json.dumps(result))
`});
assert.equal(rendered.status, 0, 'Django fixture render failed: ' + rendered.stderr);
const fixture = JSON.parse(rendered.stdout);
const css = ['vendor/bootstrap/bootstrap.min.css', 'css/tokens.css', 'css/site.css', 'css/branding.css',
    'css/admin.css', 'css/admin-ui.css', 'css/application-review.css', 'css/admin-theme.css',
    'css/admin-palette.css', 'css/admin-accessibility.css', 'css/document-preview.css'];
const assets = new Set([...css, 'js/workspace-page.js', 'js/document-preview.js']);
const report = {scope: 'Real Chrome; actual Django review/dialog partials and production assets; synthetic HTTP fixtures. Backend authorization is covered separately by Django tests.', checks: [], layouts: []};
const requests = [], errors = [], unexpected = [];
let slowStarted = 0, slowAborted = 0;
function html(mode) {
    const section = mode === 'legacy' ? fixture.applicant_documents + fixture.member_document_card : fixture.submission_review;
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Synthetic applicant preview QA</title>${css.map(file => `<link rel="stylesheet" href="/static/${file}">`).join('')}
        <script src="/static/js/workspace-page.js"></script></head><body class="admin-workspace applicant-review-workspace">
        <main id="main-content" style="padding:2rem"><div class="applicant-review-page"><h1>Application review</h1>${section}</div></main>
        ${fixture.document_preview_dialog}<script src="/static/js/document-preview.js" defer></script></body></html>`;
}
const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    requests.push({method: req.method, path: url.pathname});
    if (req.method !== 'GET') { unexpected.push(req.method); res.writeHead(405).end(); return; }
    if (url.pathname.startsWith('/static/')) {
        const file = url.pathname.slice(8);
        if (!assets.has(file)) { res.writeHead(404).end(); return; }
        res.writeHead(200, {'Content-Type': file.endsWith('.css') ? 'text/css' : 'text/javascript'});
        res.end(fs.readFileSync(path.join(root, 'static', file))); return;
    }
    if (url.pathname === '/') { res.writeHead(200, {'Content-Type': 'text/html'}).end(html(url.searchParams.get('mode'))); return; }
    if (url.pathname === '/favicon.ico') { res.writeHead(204).end(); return; }
    const privateHeaders = {'Cache-Control': 'no-store, private', 'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "sandbox; default-src 'none'", 'X-Content-Type-Options': 'nosniff'};
    if (url.pathname === '/fixture/forbidden') { res.writeHead(403, privateHeaders).end('Forbidden'); return; }
    if (url.pathname === '/fixture/missing') { res.writeHead(404, privateHeaders).end('Unavailable'); return; }
    if (url.pathname === '/fixture/redirect') { res.writeHead(302, {Location: '/fixture/login'}).end(); return; }
    if (url.pathname === '/fixture/html' || url.pathname === '/fixture/login') {
        res.writeHead(200, {...privateHeaders, 'Content-Type': 'text/html'}).end('<script>parent.previewExecuted=true</script>'); return;
    }
    if (url.pathname === '/fixture/svg') {
        res.writeHead(200, {...privateHeaders, 'Content-Type': 'image/svg+xml'}).end('<svg xmlns="http://www.w3.org/2000/svg" onload="parent.previewExecuted=true"/>'); return;
    }
    if (url.pathname === '/fixture/mislabeled') {
        res.writeHead(200, {...privateHeaders, 'Content-Type': 'application/pdf'}).end('<script>parent.previewExecuted=true</script>'); return;
    }
    if (url.pathname === '/fixture/broken-image') {
        res.writeHead(200, {...privateHeaders, 'Content-Type': 'image/png'}).end(Buffer.from(fixture.png, 'base64').subarray(0, 9)); return;
    }
    if (url.pathname === '/fixture/oversize') {
        res.writeHead(200, {...privateHeaders, 'Content-Type': 'application/pdf', 'Content-Length': 21 * 1024 * 1024});
        res.write('%PDF-'); return;
    }
    if (url.pathname === '/fixture/stream-oversize') {
        res.writeHead(200, {...privateHeaders, 'Content-Type': 'application/pdf'});
        res.write('%PDF-'); res.end(Buffer.alloc(21 * 1024 * 1024, 32)); return;
    }
    if (url.pathname === '/fixture/slow') {
        slowStarted++;
        res.writeHead(200, {...privateHeaders, 'Content-Type': 'image/png'}); res.write(Buffer.from(fixture.png, 'base64').subarray(0, 8));
        const timer = setTimeout(() => res.end(Buffer.from(fixture.png, 'base64').subarray(8)), 1500);
        res.on('close', () => { if (!res.writableEnded) slowAborted++; clearTimeout(timer); }); return;
    }
    let kind;
    if (url.pathname === '/fixture/jpeg') kind = 'jpeg';
    else if (url.pathname.endsWith('/document/1')) kind = 'pdf';
    else if (url.pathname.endsWith('/document/2') || url.pathname.endsWith('/document/3') || url.pathname.includes('/photo/')) kind = 'png';
    if (!kind) { unexpected.push(url.pathname); res.writeHead(404).end(); return; }
    res.writeHead(200, {...privateHeaders, 'Content-Type': kind === 'pdf' ? 'application/pdf' : 'image/' + kind,
        'Content-Disposition': `${url.searchParams.has('preview') ? 'inline' : 'attachment'}; filename="synthetic.${kind}"`});
    res.end(Buffer.from(fixture[kind], 'base64'));
});
async function imageReady(page) {
    await page.waitForFunction(() => {const image = document.querySelector('[data-document-preview-viewer] img'); return image?.complete && image.naturalWidth > 0;});
}
async function close(page) {
    await page.locator('[data-document-preview-close]').click();
    await page.waitForFunction(() => !document.querySelector('dialog').open);
}
async function inject(page, name, title = name) {
    await page.evaluate(({name, title}) => {
        document.querySelector('#test-preview')?.remove();
        const link = document.createElement('a'); link.id = 'test-preview'; link.href = '/fixture/' + name;
        link.dataset.documentPreview = ''; link.dataset.previewTitle = title; link.textContent = title;
        document.querySelector('main').append(link);
    }, {name, title});
    await page.locator('#test-preview').click();
}
(async () => {
    fs.mkdirSync(output, {recursive: true});
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = `http://127.0.0.1:${server.address().port}`;
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
        await context.addInitScript(() => {
            window.previewExecuted = false; window.qaURLs = []; window.qaRevoked = []; window.qaFetches = [];
            const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL), nativeFetch = window.fetch.bind(window);
            URL.createObjectURL = blob => {const url = create(blob); window.qaURLs.push(url); return url;};
            URL.revokeObjectURL = url => {window.qaRevoked.push(url); revoke(url);};
            window.fetch = (input, options) => {
                window.qaFetches.push({input: String(input), credentials: options?.credentials, cache: options?.cache, redirect: options?.redirect});
                return nativeFetch(input, options);
            };
        });
        const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
        await page.goto(origin); await page.locator('a[data-preview-title="Synthetic PNG"]').click(); await imageReady(page);
        assert.equal(await page.locator('dialog').evaluate(element => element.open), true);
        assert.equal(await page.locator('[data-document-preview-close]').evaluate(element => element === document.activeElement), true);
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('[data-document-preview-download]').evaluate(element => element === document.activeElement), true);
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('[data-document-preview-close]').evaluate(element => element === document.activeElement), true);
        assert.equal(context.pages().length, 1); assert.equal(page.url(), origin + '/');
        assert.equal(await page.locator('[data-document-preview-download]').getAttribute('href'), origin + '/programs/1/1/document/2');
        const downloadEvent = page.waitForEvent('download'); await page.locator('[data-document-preview-download]').click();
        const file = await downloadEvent; assert.equal(file.suggestedFilename(), 'synthetic.png'); await file.delete();
        await page.keyboard.press('Escape'); await page.waitForFunction(() => !document.querySelector('dialog').open);
        assert.equal(await page.evaluate(() => document.activeElement.dataset.previewTitle), 'Synthetic PNG');
        assert.equal(await page.locator('[data-document-preview-viewer] > *').count(), 0);
        assert.deepEqual(await page.evaluate(() => window.qaURLs), await page.evaluate(() => window.qaRevoked));
        report.checks.push('PNG popup, same page/no tab, real download, Escape, focus return and object URL release');

        await page.locator('a[data-preview-title="Synthetic PDF"]').click();
        await page.waitForFunction(() => document.querySelector('[data-document-preview-viewer] iframe')?.src.startsWith('blob:'));
        await page.waitForTimeout(1500); // Allow native PDF renderer to paint before its screenshot.
        const pdfViewer = page.frames().find(frame => frame.url().startsWith('chrome-extension://') && frame.url().endsWith('/index.html'));
        assert(pdfViewer, 'Chrome must open its native PDF viewer inside the popup');
        await pdfViewer.getByText('Synthetic document preview', {exact: true}).waitFor();
        const renderers = await Promise.all(page.frames().map(frame => frame.locator('embed[type="application/x-google-chrome-pdf"]').count()));
        assert(renderers.some(count => count > 0), 'Native PDF renderer must be present');
        await page.screenshot({path: path.join(output, '1440-pdf.png')});
        assert.equal(await page.locator('[data-document-preview-viewer] iframe').getAttribute('sandbox'), null);
        assert.equal(context.pages().length, 1); await close(page);
        report.checks.push('Real PDF rendered through Chrome PDF embed inside Blob iframe; no relaxed attachment response headers');

        await page.evaluate(() => Object.defineProperty(navigator, 'pdfViewerEnabled', {value: false, configurable: true}));
        await page.locator('a[data-preview-title="Synthetic PDF"]').click();
        await page.waitForFunction(() => document.querySelector('[data-document-preview-status]').textContent.includes('browser cannot display'));
        assert.equal(await page.locator('[data-document-preview-viewer] > *').count(), 0); await close(page);
        await page.evaluate(() => {delete navigator.pdfViewerEnabled;});

        await inject(page, 'jpeg'); await imageReady(page); await close(page);
        for (const [name, message] of [['forbidden', 'no longer have access'], ['missing', 'could not be loaded'],
            ['redirect', 'could not be loaded'], ['html', 'cannot be previewed safely'], ['svg', 'cannot be previewed safely'],
            ['mislabeled', 'cannot be previewed safely'], ['broken-image', 'could not be displayed'],
            ['oversize', 'too large'], ['stream-oversize', 'too large']]) {
            await inject(page, name);
            await page.waitForFunction(text => document.querySelector('[data-document-preview-status]').textContent.includes(text), message);
            assert.equal(await page.locator('[data-document-preview-viewer] > *').count(), 0);
            assert(await page.locator('[data-document-preview-download]').isVisible());
            assert(await page.locator('[data-document-preview-retry]').isVisible());
            await close(page);
        }
        assert.equal(await page.evaluate(() => window.previewExecuted), false);
        assert(!requests.some(request => request.path === '/fixture/login'), 'login redirect must not be followed');
        report.checks.push('JPEG, access denial, missing file, login redirect, HTML/SVG and false MIME rejection; declared/streamed size caps');

        await inject(page, 'missing');
        await page.waitForFunction(() => !document.querySelector('[data-document-preview-retry]').hidden);
        // Retry uses the same permitted URL; simulate the document becoming available.
        await page.route('**/fixture/missing', route => route.fulfill({contentType: 'image/png', body: Buffer.from(fixture.png, 'base64')}));
        await page.locator('[data-document-preview-retry]').click(); await imageReady(page); await close(page);
        await page.unroute('**/fixture/missing');
        await inject(page, 'slow');
        await page.waitForFunction(() => document.querySelector('[data-document-preview-content]').getAttribute('aria-busy') === 'true');
        await close(page); await page.locator('a[data-preview-title="Synthetic PNG"]').click(); await imageReady(page);
        await page.waitForTimeout(1700); assert.equal(await page.locator('[data-document-preview-title]').innerText(), 'Synthetic PNG');
        assert(slowStarted > 0 && slowAborted > 0, 'closing must abort a partially read response');
        await close(page);
        assert.deepEqual(await page.evaluate(() => window.qaURLs), await page.evaluate(() => window.qaRevoked));
        report.checks.push('Retry recovery, partial-response abort, rapid reopen keeps newest document and releases all blobs');

        for (const width of [1440, 390, 320]) for (const theme of ['light', 'dark']) {
            await page.setViewportSize({width, height: 850}); await page.evaluate(theme => document.documentElement.dataset.dashboardTheme = theme, theme);
            await page.locator('a[data-preview-title="Synthetic PNG"]').click(); await imageReady(page);
            const layout = await page.evaluate(() => {
                const issues = [];
                for (const selector of ['dialog', '[data-document-preview-close]', '[data-document-preview-download]', '[data-document-preview-viewer] img']) {
                    const box = document.querySelector(selector).getBoundingClientRect();
                    if (box.x < 0 || box.right > innerWidth || box.y < 0 || box.bottom > innerHeight || box.width <= 0 || box.height <= 0) issues.push(selector);
                }
                return {width: innerWidth, issues};
            });
            assert.deepEqual(layout.issues, [], 'Popup, image and controls stay within viewport');
            await page.screenshot({path: path.join(output, `${width}-${theme}-image.png`)}); report.layouts.push({theme, ...layout});
            await close(page);
        }
        await page.goto(origin + '/?mode=legacy');
        const legacyLinks = page.locator('a[data-document-preview]'); assert.equal(await legacyLinks.count(), 5);
        for (let index = 0; index < await legacyLinks.count(); index++) {
            assert.equal(await legacyLinks.nth(index).getAttribute('target'), null);
            await legacyLinks.nth(index).click();
            await page.waitForFunction(() => document.querySelector('[data-document-preview-viewer] > *'));
            await close(page);
        }
        // The review save replaces main content; delegation and the body-level modal survive it.
        await page.evaluate(() => {document.querySelector('main').innerHTML = '<a href="/fixture/jpeg" data-document-preview data-preview-title="Replaced review">Preview updated review</a>';});
        await page.getByText('Preview updated review').click(); await imageReady(page);
        await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: true})));
        assert.equal(await page.locator('dialog').evaluate(element => element.open), false);
        assert.deepEqual(await page.evaluate(() => window.qaURLs), await page.evaluate(() => window.qaRevoked));
        await page.getByText('Preview updated review').click(); await imageReady(page);
        await page.evaluate(() => WorkspacePage.replace());
        assert.equal(await page.locator('dialog').evaluate(element => element.open), false);
        assert.equal(await page.locator('[data-document-preview-viewer] > *').count(), 0);
        assert.deepEqual(await page.evaluate(() => window.qaURLs), await page.evaluate(() => window.qaRevoked));
        assert((await page.evaluate(() => window.qaFetches)).every(request => request.credentials === 'same-origin' && request.cache === 'no-store' && request.redirect === 'error'));
        assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); assert.equal(context.pages().length, 1);
        report.checks.push('Legacy program/member previews, updated review content, page lifecycle cleanup, six responsive/theme layouts');
        report.passed = true; console.log('PASS: private document popup, PDF/images, fallback/security cases, cancellation, focus, download and mobile layouts.');
        console.log('Evidence: ' + output);
    } finally {
        const current = browser.contexts()[0]?.pages()[0];
        if (current && !report.passed) {
            await current.screenshot({path: path.join(output, 'failure.png')});
            report.failure = await current.evaluate(() => ({status: document.querySelector('[data-document-preview-status]')?.textContent,
                viewer: document.querySelector('[data-document-preview-viewer]')?.innerHTML, fetches: window.qaFetches}));
            console.error(JSON.stringify(report.failure));
        }
        fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({...report, errors, unexpected}, null, 2));
        await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
    }
})().catch(error => {console.error(error); process.exitCode = 1; server.closeAllConnections(); server.close();});
