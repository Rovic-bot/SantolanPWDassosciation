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

function editor(state = empty, submitted = '', cards = false, oneClick = true) {
    const nodes = [], timers = new Map(), requests = [];
    let timerId = 0, nextResponseGate = null;
    function element(tagName = 'div') {
        const node = {tagName, children: [], dataset: {}, attributes: {}, handlers: {}, value: '',
            style: {setProperty(name, value) { this[name] = value; }},
            textContent: '', disabled: false, hidden: false, readOnly: false,
            validationMessage: '',
            appendChild(child) {
                if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1);
                this.children.push(child); child.parent = this; return child;
            },
            append(...items) { items.forEach(item => this.appendChild(item)); },
            replaceChildren() { this.children.forEach(child => { child.parent = null; }); this.children = []; },
            addEventListener(event, handler) { this.handlers[event] = handler; },
            setAttribute(key, value) { this.attributes[key] = value; },
            getAttribute(key) { return this.attributes[key] ?? null; },
            setCustomValidity(message) { this.validationMessage = message; },
            focus() {
                if (document.activeElement === this) return;
                document.activeElement?.handlers.blur?.();
                document.activeElement = this;
                this.handlers.focus?.();
            }};
        nodes.push(node); return node;
    }
    const document = {createElement: element, getElementById: id => nodes.find(node => node.id === id)};
    for (const match of (cards ? vaultTemplate : template).matchAll(/id="([^"]+)"/g)) element().id = match[1];
    const data = element(); data.id = 'ewaf-weight-state'; data.textContent = JSON.stringify(state);
    const form = element('form'); form.id = 'ewaf-configuration-form'; form.dataset.oneClick = String(oneClick);
    if (cards) form.dataset.vaultLayout = 'cards';
    form.elements = Object.fromEntries(Object.entries({slider_proposal: submitted, expected: 'synthetic',
        csrfmiddlewaretoken: 'synthetic', weight_review: '', calculation_method: 'ewaf-ses-4ps-es-pa-hm-dataset-v1'})
        .map(([name, value]) => [name, {value}]));
    form.elements.accept_derived_weights = Object.assign(element('input'), {type: 'checkbox', checked: false});
    const buttons = ['DRAFT', 'LOCKED'].map(value => Object.assign(element('button'), {value, disabled: true}));
    form.querySelectorAll = () => buttons;
    const runtime = {document, FormData, window: {location: {href: '/synthetic-vault/'}},
        setTimeout(fn) { timers.set(++timerId, fn); return timerId; }, clearTimeout(id) { timers.delete(id); },
        async fetch(url, options) {
            const proposal = JSON.parse(options.body.get('slider_proposal'));
            requests.push({url, method: options.body.get('calculation_method'), action: options.body.get('action'), proposal});
            const gate = nextResponseGate; nextResponseGate = null;
            if (gate) await gate;
            // AHP mathematics is tested through the actual Django service. This fixture supplies its response shape.
            return {ok: true, headers: {get: () => 'application/json'}, json: async () => ({
                rows: proposal.order.map(code => ({code, name: code, target: '25.00', actual: '25.00'})),
                consistency: {result: 'PASSED', CR: '0', RI: '0.90', criteria_count: 4},
                token: 'synthetic-review-' + requests.length, storage_errors: []})};
        }};
    runtime.WorkspacePage = {run: initialize => initialize({fetch: runtime.fetch})};
    vm.runInNewContext(source, runtime);
    return {nodes, buttons, requests, form, get: document.getElementById,
        read: () => JSON.parse(form.elements.slider_proposal.value || 'null'),
        async flush() { for (const [id, fn] of [...timers]) { timers.delete(id); await fn(); } },
        holdNextResponse() {
            let release;
            nextResponseGate = new Promise(resolve => { release = resolve; });
            return release;
        },
        type(code, value) {
            const number = document.getElementById('weight-number-' + code);
            assert.equal(number.disabled, false, code + ' number must be enabled');
            assert.equal(number.readOnly, false, code + ' number must be editable');
            number.focus(); number.value = String(value); number.handlers.input();
        },
        commit(code, enter = false) {
            const number = document.getElementById('weight-number-' + code);
            if (enter) {
                let prevented = false;
                number.handlers.keydown({key: 'Enter', preventDefault() { prevented = true; }});
                assert.ok(prevented, 'Enter must commit the number without submitting the form');
            } else number.handlers.change();
            number.handlers.blur?.(); document.activeElement = null;
        },
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
    assert.equal(page.nodes.filter(node => node.type === 'number').length, 4);
    assert.equal(page.read(), null);
    assert.equal(page.get('weight-total').textContent, 'Not set');
    assert.ok(page.buttons.every(button => button.disabled));
    await page.flush(); assert.equal(page.requests.length, 0, 'loading must not invent or calculate a vector');
    for (const code of codes) {
        const range = page.get('weight-' + code);
        assert.equal(range.min, 0); assert.equal(range.max, 100); assert.equal(range.step, '0.01');
        assert.equal(page.get('weight-output-' + code).textContent, 'Not set');
        const number = page.get('weight-number-' + code);
        assert.equal(number.step, '0.01');
        assert.equal(number.value, '', 'unselected weights must not appear as numeric defaults');
        assert.equal(number.disabled, code !== 'SES');
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
    assert.equal(page.get('weight-number-HM').readOnly, false);
    assert.equal(page.get('weight-number-PA').readOnly, true, 'last priority remains the automatic remainder');
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

    // Typing follows the production priority cascade without replacing focused text.
    const typed = editor({...empty, proposal: saved, resetProposal: saved, approvableProposal: saved}, '', cards);
    await typed.flush();
    assert.equal(typed.get('weight-number-PA').min, '12.50');
    assert.equal(typed.get('weight-number-PA').max, '19.44', '50% top weight requires at least 5.56% in the last row');
    typed.type('SES', '55.55');
    assert.equal(typed.get('weight-number-SES').value, '55.55');
    typed.type('SES', '60');
    assert.deepEqual(typed.read().weights, {SES: 6000, ES: 2000, PA: 1200, HM: 800},
        'all keystrokes in a focused edit use the original allocation, without cumulative rounding drift');
    assert.equal(Number(typed.get('weight-SES').value), 60);
    assert.equal(typed.get('weight-number-ES').value, '20.00');
    assert.equal(typed.get('weight-number-HM').value, '8.00');
    assert.equal(typed.get('weight-total').textContent, '100.00%');
    typed.commit('SES', true);
    assert.equal(typed.get('weight-number-SES').value, '60.00');
    typed.type('ES', '22');
    assert.equal(typed.read().weights.SES, 6000, 'typing preserves earlier-priority weights');
    typed.commit('ES');
    assert.equal(typed.get('weight-number-ES').value, '22.00');

    // Invalid visible drafts cannot silently save the last valid proposal or use its preview.
    for (const invalid of ['', '-1', '101', '20', '12.345', 'Infinity', 'abc']) {
        typed.get('reset-weights').handlers.click(); await typed.flush();
        assert.ok(typed.buttons.every(button => !button.disabled));
        typed.type('PA', invalid);
        assert.equal(typed.get('weight-number-PA').value, invalid);
        assert.deepEqual(typed.read(), saved, 'invalid input leaves the accepted proposal unchanged');
        assert.equal(typed.get('weight-number-PA').getAttribute('aria-invalid'), 'true');
        assert.ok(typed.get('weight-number-PA').validationMessage);
        assert.equal(typed.get('weight-error-PA').hidden, false);
        assert.ok(typed.get('weight-error-PA').textContent);
        assert.ok(typed.buttons.every(button => button.disabled));
        assert.equal(typed.get('preview-weights').disabled, true);
        assert.equal(typed.get('weight-preview').hidden, true);
        const previousRequests = typed.requests.length;
        await typed.flush();
        assert.equal(typed.requests.length, previousRequests, 'invalid text must not schedule a preview');
    }
    typed.type('PA', '17'); typed.commit('PA'); await typed.flush();
    assert.deepEqual(typed.read().weights, {SES: 5000, ES: 2500, PA: 1700, HM: 800});
    assert.equal(typed.get('weight-number-PA').getAttribute('aria-invalid'), 'false');
    assert.equal(typed.get('weight-number-PA').validationMessage, '');
    assert.equal(typed.get('weight-error-PA').hidden, true);
    assert.equal(typed.buttons[0].disabled, false);
    assert.equal(typed.buttons[1].disabled, true, 'typing must preserve the saved-draft approval gate');

    // Switching to another control clears obsolete text drafts and restores synchronized values.
    typed.type('PA', ''); typed.move('SES', 60);
    assert.equal(typed.get('weight-error-PA').hidden, true);
    assert.equal(Number(typed.get('weight-number-PA').value) * 100, typed.read().weights.PA);
    typed.type('ES', ''); typed.up('HM');
    assert.equal(typed.get('weight-error-ES').hidden, true);
    assert.equal(typed.get('weight-number-PA').readOnly, true);
    typed.type('SES', ''); typed.get('reset-weights').handlers.click();
    assert.deepEqual(typed.read(), saved);
    assert.equal(typed.get('weight-number-SES').value, '50.00');
    assert.equal(typed.get('weight-error-SES').hidden, true);

    // The first number can be entered a character at a time without creating defaults.
    const firstTyped = editor(empty, '', cards);
    firstTyped.type('SES', '5');
    assert.equal(firstTyped.get('weight-number-SES').value, '5');
    assert.equal(firstTyped.read(), null, 'an invalid partial first entry does not install a proposal');
    firstTyped.type('SES', '50'); firstTyped.commit('SES');
    assert.deepEqual(firstTyped.read().weights, {SES: 5000, ES: 1667, PA: 1667, HM: 1666});
    assert.equal(firstTyped.get('weight-number-HM').readOnly, true);
    assert.equal(firstTyped.get('weight-number-ES').disabled, false);

    // A late successful preview cannot re-enable save after an invalid edit.
    const race = editor({...empty, proposal: saved, resetProposal: saved,
        approvableProposal: saved, requireSavedProposal: false}, '', cards);
    await race.flush();
    const release = race.holdNextResponse();
    race.type('PA', '17');
    const inFlight = race.flush();
    race.type('PA', '');
    release(); await inFlight;
    assert.ok(race.buttons.every(button => button.disabled));
    assert.equal(race.get('weight-preview').hidden, true);
    assert.equal(race.get('preview-weights').disabled, true);
    assert.equal(race.get('weight-number-PA').value, '');
    console.log('PASS (' + (cards ? 'Vault cards' : 'shared editor') + '): slider/number sync, typing anchors, invalid drafts, stale previews, first choice, priority, reset and approval gating. DOM simulation; no browser layout claim.');
    }

    // The non-one-click shared editor uses an explicit preview and acceptance checkbox.
    const sharedInitial = {order: codes, weights: {SES: 5000, ES: 2500, PA: 1500, HM: 1000}};
    const manual = editor({...empty, proposal: sharedInitial, resetProposal: sharedInitial,
        hasSavedWeights: false}, '', false, false);
    const acceptance = manual.form.elements.accept_derived_weights;
    const accept = () => { acceptance.checked = true; acceptance.handlers.change(); };
    const preview = manual.get('preview-weights');
    assert.equal(preview.disabled, false);
    assert.equal(manual.buttons[1].disabled, true, 'an initial unsaved proposal cannot be approved without review');
    await manual.flush();
    assert.equal(manual.requests.length, 0, 'the manual editor does not calculate automatically');
    await preview.handlers.click();
    const originalToken = manual.form.elements.weight_review.value;
    assert.ok(originalToken);
    assert.equal(manual.buttons[1].disabled, true, 'preview alone does not imply acceptance');
    accept(); assert.equal(manual.buttons[1].disabled, false);

    manual.type('PA', '');
    assert.equal(preview.disabled, true);
    assert.equal(manual.form.elements.weight_review.value, '', 'invalid input discards the reviewed token');
    assert.equal(manual.buttons[1].disabled, true);
    manual.get('reset-weights').handlers.click();
    assert.equal(preview.disabled, false, 'reset must restore the manual Calculate button after invalid input');
    assert.equal(manual.get('weight-number-PA').value, '15.00');
    assert.equal(manual.get('weight-error-PA').hidden, true);
    assert.equal(acceptance.checked, false);
    assert.equal(manual.form.elements.weight_review.value, '');
    assert.equal(manual.buttons[1].disabled, true, 'resetting an unsaved proposal is not approval');
    await preview.handlers.click();
    const resetToken = manual.form.elements.weight_review.value;
    assert.ok(resetToken && resetToken !== originalToken, 'reset recovery requires a fresh review');
    assert.equal(manual.buttons[1].disabled, true);
    accept(); assert.equal(manual.buttons[1].disabled, false);

    manual.type('PA', ''); manual.up('HM');
    assert.equal(preview.disabled, false, 'priority changes must restore Calculate after invalid input');
    assert.equal(manual.get('weight-error-PA').hidden, true);
    assert.equal(manual.get('weight-number-PA').readOnly, true);
    assert.deepEqual(manual.read().order, ['SES', 'ES', 'HM', 'PA']);
    assert.equal(manual.form.elements.weight_review.value, '');
    assert.equal(acceptance.checked, false, 'priority changes revoke acceptance');
    accept(); assert.equal(manual.buttons[1].disabled, true, 'acceptance without a fresh token is insufficient');
    await preview.handlers.click();
    assert.ok(manual.form.elements.weight_review.value !== resetToken);
    assert.equal(acceptance.checked, false, 'calculating again requires explicit acceptance of that result');
    assert.equal(manual.buttons[1].disabled, true);
    accept(); assert.equal(manual.buttons[1].disabled, false);
    console.log('PASS (manual shared editor): invalid draft reset/reorder restores Calculate; fresh review and explicit acceptance gate approval.');
})().catch(error => { console.error(error); process.exitCode = 1; });
