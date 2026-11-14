// Native Chromium regression for the production Vault editor, without authentication or a database.
// The actual Django partial/CSS/JS are used; only context and AHP response data are synthetic.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = path.resolve(__dirname, '..');
const output = path.resolve(process.env.QA_OUTPUT || path.join(root, '.local/typed-weight-qa'));
const python = process.env.QA_PYTHON || [path.join(root, '.venv/Scripts/python.exe'),
    path.resolve(root, '../../santolan-pwd-system/.venv/Scripts/python.exe')].find(file => fs.existsSync(file)) || 'python';
const rendered = spawnSync(python, ['-'], {cwd: root, encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8'}, input: String.raw`
from pathlib import Path
from django.conf import settings
settings.configure(USE_I18N=False, SECRET_KEY='synthetic-template-only')
import django
django.setup()
from django import forms
from django.template import Context, Engine
class Notes(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))
engine = Engine(dirs=[str(Path.cwd() / 'templates')])
print(engine.get_template('ewaf/vault_weight_editor.html').render(Context({
    'active': None, 'form': Notes(), 'can_authorize': True,
    'can_configure': True, 'is_ses': True, 'is_composite': False,
})))
`});
assert.equal(rendered.status, 0, 'Standalone Django template rendering failed: ' + rendered.stderr);
assert(!rendered.stdout.includes('{%'), 'Django tags must be rendered, not approximated');
const codes = ['SES', 'ES', 'PA', 'HM'];
const names = {SES: 'Socioeconomic Status', ES: 'Employment Status', PA: 'Previous Assistance', HM: 'Household Members'};
const saved = {order: codes, weights: {SES: 5000, ES: 2500, PA: 1500, HM: 1000}};
const css = ['vendor/bootstrap/bootstrap.min.css', 'css/tokens.css', 'css/site.css', 'css/branding.css',
    'css/action-feedback.css', 'css/admin.css', 'css/admin-ui.css', 'css/program-workflow.css', 'css/reference-ui.css',
    'css/ewaf-weights.css', 'css/admin-theme.css', 'css/admin-filters.css', 'css/ewaf-vault.css',
    'css/receipt-details.css', 'css/admin-motion.css', 'css/admin-palette.css', 'css/admin-accessibility.css'];
const assets = new Set([...css, 'js/workspace-page.js', 'js/ewaf-weights.js']);
function html(hasSaved, theme) {
    const state = {criteria: codes, names, displayNames: names, proposal: hasSaved ? saved : null,
        resetProposal: hasSaved ? saved : null, approvableProposal: hasSaved ? saved : null,
        requireSavedProposal: true, startingLabel: 'No weights selected.'};
    return `<!doctype html><html lang="en" data-dashboard-theme="${theme}"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1"><title>Synthetic weight editor QA</title>
        ${css.map(file => `<link rel="stylesheet" href="/static/${file}">`).join('')}
        <script src="/static/js/workspace-page.js"></script></head><body class="admin-workspace">
        <main id="main-content"><div class="configuration-vault"><h1>EWAF Configuration Vault</h1>
        <form method="post" id="ewaf-configuration-form" data-one-click="true" data-vault-layout="cards">
        <input type="hidden" name="csrfmiddlewaretoken" value="synthetic"><input type="hidden" name="expected" value="synthetic">
        <input type="hidden" name="slider_proposal"><input type="hidden" name="weight_review">
        <input type="hidden" name="calculation_method" value="ewaf-ses-4ps-es-pa-hm-dataset-v1">
        ${rendered.stdout}</form></div></main><script id="ewaf-weight-state" type="application/json">${JSON.stringify(state)}</script>
        <script>window.qaSubmits = 0; document.querySelector('form').addEventListener('submit', event => {
        event.preventDefault(); window.qaSubmits++; });</script><script src="/static/js/ewaf-weights.js" defer></script></body></html>`;
}
function multipart(body, name) {
    const match = body.match(new RegExp('name="' + name + '"\\r\\n\\r\\n([^\\r]*)'));
    return match && match[1];
}
const report = {scope: 'Real Chrome; actual Django partial and production assets; synthetic preview only. No authenticated full-page, backend AHP, persistence or approval claim.',
    checks: [], layouts: [], requests: []};
async function read(page) { return JSON.parse(await page.locator('[name=slider_proposal]').inputValue() || 'null'); }
async function type(page, code, value) {
    const input = page.locator('#weight-number-' + code);
    await input.focus(); await input.press('ControlOrMeta+A'); await input.press('Backspace');
    if (value) await input.pressSequentially(value, {delay: 25});
}
async function ready(page) {
    await page.waitForFunction(() => !document.querySelector('#weight-preview').hidden &&
        !document.querySelector('button[value=DRAFT]').disabled);
}
async function synced(page) {
    const proposal = await read(page);
    assert.equal(Object.values(proposal.weights).reduce((sum, value) => sum + value, 0), 10000);
    assert.equal(await page.locator('#weight-total').innerText(), '100.00%');
    for (const code of codes) {
        assert.equal(Math.round(Number(await page.locator('#weight-' + code).inputValue()) * 100), proposal.weights[code]);
        assert.equal(Math.round(Number(await page.locator('#weight-number-' + code).inputValue()) * 100), proposal.weights[code]);
        assert(await page.locator('#weight-number-' + code).evaluate(input => input.validity.valid), code + ' must pass native number validity');
    }
    await page.locator('[name=reason]').fill('Synthetic browser test; never submitted.');
    assert(await page.locator('form').evaluate(form => form.checkValidity()), 'valid proposal must pass native form constraints');
}
(async () => {
    fs.mkdirSync(output, {recursive: true});
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const errors = [], unexpected = [];
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
        await context.route('**/*', async route => {
            const request = route.request(), url = new URL(request.url());
            if (url.origin !== 'http://weight-editor.test') { unexpected.push(request.url()); return route.abort(); }
            if (request.method() === 'POST') {
                const action = multipart(request.postData() || '', 'action');
                if (action !== 'PREVIEW_WEIGHTS') { unexpected.push('Unexpected write: ' + action); return route.abort(); }
                const proposal = JSON.parse(multipart(request.postData(), 'slider_proposal'));
                report.requests.push({action, proposal});
                // Deliberately do not simulate AHP mathematics or authenticate/authorize any configuration.
                return route.fulfill({contentType: 'application/json', body: JSON.stringify({token: 'synthetic-preview',
                    rows: proposal.order.map(code => ({code, name: names[code], target: (proposal.weights[code] / 100).toFixed(2), actual: '25.00'})),
                    consistency: {result: 'PASSED', CR: '0', RI: '0.90', criteria_count: 4}, storage_errors: []})});
            }
            if (url.pathname.startsWith('/static/')) {
                const file = url.pathname.slice(8);
                if (!assets.has(file)) return route.fulfill({status: 404, body: ''});
                return route.fulfill({contentType: file.endsWith('.css') ? 'text/css' : 'text/javascript',
                    body: fs.readFileSync(path.join(root, 'static', file))});
            }
            return route.fulfill({contentType: 'text/html', body: html(url.searchParams.has('saved'), url.searchParams.get('theme') || 'light')});
        });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.goto('http://weight-editor.test/');
        await page.locator('#weight-number-SES').waitFor();
        assert.equal(await read(page), null);
        assert.equal(await page.locator('#weight-total').innerText(), 'Not set');
        for (const code of codes) assert.equal(await page.locator('#weight-number-' + code).inputValue(), '');
        assert.equal(await page.locator('#weight-number-ES').isDisabled(), true);
        await type(page, 'SES', '5');
        assert.equal(await read(page), null, 'partial first entry cannot silently initialize defaults');
        assert.equal(await page.locator('#weight-number-SES').inputValue(), '5');
        await page.locator('#weight-number-SES').pressSequentially('0.01', {delay: 25});
        assert.equal((await read(page)).weights.SES, 5001);
        await page.locator('#weight-number-SES').press('Enter'); await synced(page); await ready(page);
        assert.equal(await page.locator('button[value=LOCKED]').isDisabled(), true, 'new weights retain draft gate');
        assert.equal(await page.evaluate(() => window.qaSubmits), 0);
        report.checks.push('First proposal entered character by character with 0.01 precision; no invented default, exact total, no Enter submit');

        await page.goto('http://weight-editor.test/?saved'); await ready(page);
        await type(page, 'SES', '55.55');
        await page.locator('#weight-number-SES').press('ControlOrMeta+A');
        await page.locator('#weight-number-SES').pressSequentially('60');
        assert.deepEqual((await read(page)).weights, {SES: 6000, ES: 2000, PA: 1200, HM: 800}, 'focused edits preserve original cascade proportions');
        await page.locator('#weight-number-SES').press('Tab');
        assert.equal(await page.locator('#weight-number-SES').inputValue(), '60.00', 'native change/blur normalizes');
        await synced(page);
        await page.locator('#reset-weights').click(); await ready(page);
        await type(page, 'PA', '17.01'); await page.locator('#weight-number-PA').press('Enter');
        assert.deepEqual((await read(page)).weights, {SES: 5000, ES: 2500, PA: 1701, HM: 799});
        await synced(page); await ready(page);
        assert.equal(await page.evaluate(() => window.qaSubmits), 0);
        report.checks.push('Typing preserves earlier priorities and focus anchor; blur/Enter normalization; synchronized slider/number/100% total');

        for (const boundary of ['min', 'max']) {
            await page.locator('#reset-weights').click(); await ready(page);
            const value = await page.locator('#weight-number-PA').getAttribute(boundary);
            await type(page, 'PA', value); await page.locator('#weight-number-PA').press('Tab');
            await page.locator('#weight-number-PA').focus(); await synced(page);
        }
        await page.locator('#reset-weights').click(); await ready(page);
        await page.locator('#weight-number-PA').focus(); await page.locator('#weight-number-PA').press('ArrowUp');
        assert.equal((await read(page)).weights.PA, 1501, 'native number spin keyboard advances one hundredth');
        await page.locator('#weight-number-PA').press('Tab'); await synced(page);
        report.checks.push('Native number/form validity including minimum/maximum endpoints, blur/refocus and ArrowUp increment');

        for (const value of ['', '101', '-1', '12.345', '1e2']) {
            await page.locator('#reset-weights').click(); await ready(page);
            const count = report.requests.length;
            await type(page, 'PA', value);
            assert.deepEqual(await read(page), saved, 'invalid draft must preserve accepted vector');
            assert.equal(await page.locator('#weight-number-PA').getAttribute('aria-invalid'), 'true');
            assert(await page.locator('#weight-number-PA').evaluate(input => Boolean(input.validationMessage)));
            assert(await page.locator('#weight-error-PA').isVisible());
            assert(await page.locator('#preview-weights').isDisabled());
            assert(await page.locator('#weight-preview').isHidden());
            assert(await page.locator('button[value=DRAFT]').isDisabled());
            assert(await page.locator('button[value=LOCKED]').isDisabled());
            await page.locator('#weight-number-PA').press('Enter');
            await page.waitForTimeout(400);
            assert.equal(report.requests.length, count, 'invalid draft must not cause preview requests');
            assert.equal(await page.evaluate(() => window.qaSubmits), 0);
        }
        await type(page, 'PA', '17'); await page.locator('#weight-number-PA').press('Tab'); await ready(page);
        assert.equal(await page.locator('#weight-number-PA').inputValue(), '17.00');
        assert.equal(await page.locator('#weight-number-PA').getAttribute('aria-invalid'), 'false');
        report.checks.push('Blank, out-of-range, negative, excessive precision and exponent inputs block preview/save; corrected input recovers');

        await page.locator('#reset-weights').click(); await ready(page);
        const last = page.locator('#weight-number-HM');
        assert(await last.evaluate(input => input.readOnly));
        await last.focus(); await last.press('ControlOrMeta+A'); await last.pressSequentially('99');
        assert.equal(await last.inputValue(), '10.00');
        await page.locator('#weight-PA').focus(); await page.locator('#weight-PA').press('ArrowRight');
        assert.equal((await read(page)).weights.PA, 1501); await synced(page);
        for (let i = 0; i < 3; i++) await page.getByRole('button', {name: 'Move Household Members higher in priority', exact: true}).click();
        assert.deepEqual((await read(page)).order, ['HM', 'SES', 'ES', 'PA']);
        assert(await page.locator('#weight-number-PA').evaluate(input => input.readOnly));
        assert(!(await last.evaluate(input => input.readOnly)));
        await type(page, 'HM', '55'); await last.press('Enter'); await synced(page);
        report.checks.push('Native range keyboard increments synchronize numeric controls; last row readonly follows reordering and can be edited after promotion');

        for (const width of [1440, 390, 320]) for (const theme of ['light', 'dark']) {
            await page.setViewportSize({width, height: 1100});
            await page.goto(`http://weight-editor.test/?saved&theme=${theme}`); await ready(page);
            await type(page, 'PA', '17.01'); await page.locator('#weight-number-PA').press('Tab'); await ready(page);
            await synced(page);
            const layout = await page.evaluate(() => {
                const problems = [];
                for (const element of document.querySelectorAll('.weight-row, .weight-row-heading label, .weight-number-group, .weight-number, .weight-order, .weight-range')) {
                    const box = element.getBoundingClientRect();
                    if (box.x < -1 || box.right > innerWidth + 1 || box.width < 1) problems.push(element.className || element.id);
                }
                for (const row of document.querySelectorAll('.weight-row')) {
                    const label = row.querySelector('label').getBoundingClientRect();
                    const number = row.querySelector('.weight-number-group').getBoundingClientRect();
                    if (label.right > number.left + 1 && label.bottom > number.top && number.bottom > label.top) problems.push('label/input overlap');
                }
                return {width: innerWidth, scrollWidth: document.documentElement.scrollWidth, problems,
                    numberStyle: {color: getComputedStyle(document.querySelector('.weight-number')).color,
                        background: getComputedStyle(document.querySelector('.weight-number')).backgroundColor}};
            });
            await page.screenshot({path: path.join(output, `${width}-${theme}.png`), fullPage: true});
            assert(layout.scrollWidth <= width + 1, `${width}/${theme}: document horizontal overflow ${layout.scrollWidth}`);
            assert.deepEqual(layout.problems, [], `${width}/${theme}: clipped/overlapping controls`);
            assert.notEqual(layout.numberStyle.color, layout.numberStyle.background, 'input text must contrast with its surface');
            await type(page, 'PA', '101');
            assert(await page.locator('#weight-error-PA').isVisible());
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'validation must not widen mobile page');
            await page.screenshot({path: path.join(output, `${width}-${theme}-invalid.png`), fullPage: true});
            report.layouts.push({theme, ...layout});
        }
        assert.deepEqual(errors, [], 'browser runtime errors');
        assert.deepEqual(unexpected, [], 'external requests or non-preview writes');
        report.checks.push('1440/390/320 light and dark layouts, valid/error states, no horizontal overflow or label/input overlap');
        report.passed = true;
        console.log('PASS: native Chrome typed weight controls, validation, keyboard normalization, priority/readonly behavior and six responsive theme layouts.');
        console.log(report.scope); console.log('Evidence: ' + output);
    } finally {
        fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({...report, errors, unexpected}, null, 2));
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
