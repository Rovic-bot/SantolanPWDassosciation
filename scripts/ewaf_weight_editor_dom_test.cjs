// Execute the production editor against a small DOM/event fixture, without a browser or database.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'static/js/ewaf-weights.js'), 'utf8');
const template = fs.readFileSync(path.join(root, 'templates/ewaf/weight_editor.html'), 'utf8');
const vaultTemplate = fs.readFileSync(path.join(root, 'templates/ewaf/vault_weight_editor.html'), 'utf8');
const codes = ['SES', 'ES', 'PA', 'HM'];
const empty = {proposal: null, resetProposal: null, criteria: codes,
    names: Object.fromEntries(codes.map(code => [code, code])), requireSavedProposal: true,
    approvableProposal: null, startingLabel: 'No weights selected.'};

function editor(state = empty, submitted = '', cards = false) {
    const nodes = [], timers = new Map(), requests = [];
    let timerId = 0;
    function element(tagName = 'div') {
        const node = {tagName, children: [], dataset: {}, attributes: {}, handlers: {}, value: '',
            style: {setProperty(name, value) { this[name] = value; }},
            textContent: '', disabled: false, hidden: false,
            appendChild(child) {
                if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1);
                this.children.push(child); child.parent = this; return child;
            },
            append(...items) { items.forEach(item => this.appendChild(item)); },
            replaceChildren() { this.children.forEach(child => { child.parent = null; }); this.children = []; },
            addEventListener(event, handler) { this.handlers[event] = handler; },
            setAttribute(key, value) { this.attributes[key] = value; },
            getAttribute(key) { return this.attributes[key] ?? null; },
            focus() { document.activeElement = this; }};
        nodes.push(node); return node;
    }
    const document = {createElement: element, getElementById: id => nodes.find(node => node.id === id)};
    for (const match of (cards ? vaultTemplate : template).matchAll(/id="([^"]+)"/g)) element().id = match[1];
    const data = element(); data.id = 'ewaf-weight-state'; data.textContent = JSON.stringify(state);
    const form = element('form'); form.id = 'ewaf-configuration-form'; form.dataset.oneClick = 'true';
    if (cards) form.dataset.vaultLayout = 'cards';
    form.elements = Object.fromEntries(Object.entries({slider_proposal: submitted, expected: 'synthetic',
        csrfmiddlewaretoken: 'synthetic', calculation_method: 'ewaf-ses-4ps-es-pa-hm-dataset-v1'})
        .map(([name, value]) => [name, {value}]));
    const buttons = ['DRAFT', 'LOCKED'].map(value => Object.assign(element('button'), {value, disabled: true}));
    form.querySelectorAll = () => buttons;
    const runtime = {document, FormData, window: {location: {href: '/synthetic-vault/'}},
        setTimeout(fn) { timers.set(++timerId, fn); return timerId; }, clearTimeout(id) { timers.delete(id); },
        async fetch(url, options) {
            const proposal = JSON.parse(options.body.get('slider_proposal'));
            requests.push({url, method: options.body.get('calculation_method'), action: options.body.get('action'), proposal});
            // AHP mathematics is tested through the actual Django service. This fixture supplies its response shape.
            return {ok: true, headers: {get: () => 'application/json'}, json: async () => ({
                rows: proposal.order.map(code => ({code, name: code, target: '25.00', actual: '25.00'})),
                consistency: {result: 'PASSED', CR: '0', RI: '0.90', criteria_count: 4}, storage_errors: []})};
        }};
    runtime.WorkspacePage = {run: initialize => initialize({fetch: runtime.fetch})};
    vm.runInNewContext(source, runtime);
    return {nodes, buttons, requests, form, get: document.getElementById,
        read: () => JSON.parse(form.elements.slider_proposal.value || 'null'),
        async flush() { for (const [id, fn] of [...timers]) { timers.delete(id); await fn(); } },
        move(code, percentage) {
            const range = document.getElementById('weight-' + code);
            assert.equal(range.disabled, false, code + ' must be adjustable');
            range.handlers.pointerdown(); range.value = percentage; range.handlers.input(); range.handlers.change();
        },
        up(code) { nodes.find(node => node.getAttribute('aria-label') === `Move ${code} higher in priority`).handlers.click(); }};
}

(async () => {
    for (const cards of [false, true]) {
    const page = editor(empty, '', cards);
    assert.equal(page.get('weight-editor').hidden, false);
    assert.equal(page.nodes.filter(node => node.tagName === 'input' && node.type === 'range').length, 4);
    assert.equal(page.nodes.filter(node => node.type === 'number').length, 0);
    assert.equal(page.read(), null);
    assert.equal(page.get('weight-total').textContent, 'Not set');
    assert.ok(page.buttons.every(button => button.disabled));
    await page.flush(); assert.equal(page.requests.length, 0, 'loading must not invent or calculate a vector');
    for (const code of codes) {
        const range = page.get('weight-' + code);
        assert.equal(range.min, 0); assert.equal(range.max, 100); assert.equal(range.step, '0.01');
        assert.equal(page.get('weight-output-' + code).textContent, 'Not set');
    }
    page.move('SES', 50); page.move('ES', 25); page.move('PA', 15);
    assert.deepEqual(page.read().weights, {SES: 5000, ES: 2500, PA: 1500, HM: 1000});
    assert.equal(page.get('weight-total').textContent, '100.00%');
    page.move('PA', 17);
    assert.deepEqual(page.read().weights, {SES: 5000, ES: 2500, PA: 1700, HM: 800});
    page.move('PA', 12.5);
    assert.deepEqual(page.read().weights, {SES: 5000, ES: 2500, PA: 1250, HM: 1250});
    await page.flush();
    if (cards) assert.equal(page.get('weight-consistency').dataset.result, 'PASSED');
    assert.equal(page.requests[0].action, 'PREVIEW_WEIGHTS');
    assert.equal(page.requests[0].method, 'ewaf-ses-4ps-es-pa-hm-dataset-v1');
    assert.equal(page.buttons[0].disabled, false);
    assert.equal(page.buttons[1].disabled, true, 'unsaved weights cannot be approved');
    for (let i = 0; i < 3; i++) page.up('HM');
    assert.equal(page.read().order[0], 'HM');
    assert.equal(page.get('weight-HM').disabled, false);
    assert.equal(page.get('weight-PA').disabled, true);
    page.get('reset-weights').handlers.click();
    assert.equal(page.read(), null); assert.ok(page.buttons.every(button => button.disabled));
    assert.equal(page.get('weight-preview').hidden, true);
    assert.equal(page.get('preview-weights').disabled, true);
    const count = page.requests.length;
    await page.flush(); assert.equal(page.requests.length, count, 'reset cancels pending calculations');
    for (let i = 0; i < 3; i++) page.up('HM');
    assert.equal(page.read(), null, 'priority alone does not select weights');
    page.move('HM', 55);
    assert.deepEqual(page.read(), {order: ['HM', 'SES', 'ES', 'PA'], weights: {HM: 5500, SES: 1500, ES: 1500, PA: 1500}});

    const saved = {order: codes, weights: {SES: 5000, ES: 2500, PA: 1500, HM: 1000}};
    const reopened = editor({...empty, proposal: saved, resetProposal: saved, approvableProposal: saved}, JSON.stringify(saved), cards);
    await reopened.flush(); assert.ok(reopened.buttons.every(button => !button.disabled));
    reopened.move('PA', 17); await reopened.flush(); assert.equal(reopened.buttons[1].disabled, true);
    reopened.get('reset-weights').handlers.click(); await reopened.flush();
    assert.deepEqual(reopened.read(), saved); assert.equal(reopened.buttons[1].disabled, false);
    const rejectedSave = editor(empty, JSON.stringify(saved), cards);
    assert.deepEqual(rejectedSave.read(), saved, 'a rejected save retains the submitted proposal');
    console.log('PASS (' + (cards ? 'Vault cards' : 'shared editor') + '): four sliders, first gesture, cascade, priority, reset, preview and approval gating. DOM simulation; no browser layout claim.');
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
