/* Integer hundredths of a percentage keep every displayed total exactly 100%. */
((root) => {
    'use strict';
    const versions = [['SES', 'ES', 'PA', 'HM'], ['HI', 'SI', 'ES', 'PA', 'HM'], ['SI', 'ES', 'PA', 'ND']];
    const copy = value => JSON.parse(JSON.stringify(value));
    function valid(proposal) {
        if (!proposal || !Array.isArray(proposal.order) || !proposal.weights) return false;
        const codes = versions.find(items => items.length === proposal.order.length && items.every(code => proposal.order.includes(code)));
        if (!codes || new Set(proposal.order).size !== codes.length || Object.keys(proposal.weights).length !== codes.length) return false;
        const values = proposal.order.map(code => proposal.weights[code]);
        return values.every(value => Number.isInteger(value) && value > 0) &&
            values.reduce((a, b) => a + b, 0) === 10000 &&
            values.every((value, i) => i === 0 || value <= values[i - 1]) && values[0] <= 9 * values[values.length - 1];
    }
    function candidate(proposal, index, value) {
        const next = {order: proposal.order, weights: {...proposal.weights}}, tail = proposal.order.slice(index + 1);
        const prefix = proposal.order.slice(0, index).reduce((sum, code) => sum + proposal.weights[code], 0);
        const remaining = 10000 - prefix - value;
        const total = tail.reduce((sum, code) => sum + proposal.weights[code], 0);
        if (!tail.length || remaining <= 0) return null;
        next.weights[proposal.order[index]] = value;
        const remainders = tail.map((code, i) => {
            const product = remaining * proposal.weights[code];
            next.weights[code] = Math.floor(product / total);
            return {code, remainder: product % total, i};
        }).sort((a, b) => b.remainder - a.remainder || a.i - b.i);
        const missing = remaining - tail.reduce((sum, code) => sum + next.weights[code], 0);
        for (let i = 0; i < missing; i++) next.weights[remainders[i].code]++;
        return valid(next) ? next : null;
    }
    function choices(proposal, index) {
        if (index === proposal.order.length - 1) return [proposal.weights[proposal.order[index]]];
        const prefix = proposal.order.slice(0, index).reduce((sum, code) => sum + proposal.weights[code], 0);
        const remaining = 10000 - prefix, tail = proposal.order.slice(index + 1);
        const total = tail.reduce((sum, code) => sum + proposal.weights[code], 0);
        const first = proposal.weights[tail[0]] / total, last = proposal.weights[tail[tail.length - 1]] / total;
        // Largest-remainder allocation differs from each exact quota by < 1.
        // These are necessary outer bounds; verify the integer endpoints below.
        let lower = Math.max(1, Math.ceil((remaining * first - 1) / (1 + first) - 1e-9));
        let upper = Math.min(remaining - tail.length, index ? proposal.weights[proposal.order[index - 1]] : 10000,
            Math.floor((index ? remaining - (proposal.weights[proposal.order[0]] / 9 - 1) / last :
                (9 * remaining * last + 9) / (1 + 9 * last)) + 1e-9));
        while (lower < upper && !candidate(proposal, index, lower)) lower++;
        while (upper > lower && !candidate(proposal, index, upper)) upper--;
        return [lower, upper];
    }
    function cascade(proposal, index, requested) {
        if (!valid(proposal) || index < 0 || index > proposal.order.length - 2) return copy(proposal);
        const [lower, upper] = choices(proposal, index);
        const nearest = Math.max(lower, Math.min(upper, Math.round(requested)));
        // Rounding can create boundary gaps; never assume a continuous feasible set.
        for (let distance = 0; distance <= upper - lower; distance++) {
            for (const value of [nearest - distance, nearest + distance]) {
                if (value >= lower && value <= upper) {
                    const next = candidate(proposal, index, value);
                    if (next) return next;
                }
            }
        }
        return copy(proposal);
    }
    function reorder(proposal, index, direction) {
        const next = copy(proposal), other = index + direction;
        if (other < 0 || other >= proposal.order.length) return next;
        const values = proposal.order.map(code => proposal.weights[code]);
        [next.order[index], next.order[other]] = [next.order[other], next.order[index]];
        next.order.forEach((code, i) => { next.weights[code] = values[i]; });
        return next;
    }
    function begin(order, requested) {
        // No starting vector is installed on page load. On the first gesture,
        // the user's top weight leaves an initially equal share for lower rows.
        const share = Math.floor(10000 / order.length), remainder = 10000 % order.length;
        const allocation = {order: [...order], weights: Object.fromEntries(
            order.map((code, index) => [code, share + (index < remainder ? 1 : 0)]))};
        return cascade(allocation, 0, requested);
    }
    if (typeof module !== 'undefined') module.exports = {valid, cascade, reorder, choices, begin};
    if (!root.document) return;
    root.WorkspacePage.run(({fetch}) => {
    const form = document.getElementById('ewaf-configuration-form');
    if (!form) return;
    const oneClick = form.dataset.oneClick === 'true';
    const vaultCards = form.dataset.vaultLayout === 'cards';
    const state = JSON.parse(document.getElementById('ewaf-weight-state').textContent);
    const displayNames = vaultCards ? state.displayNames || state.names : state.names;
    const codes = state.criteria || state.proposal.order;
    let pendingOrder = [...codes];
    const initial = copy(state.resetProposal);
    let submitted;
    try { submitted = JSON.parse(form.elements.slider_proposal.value || 'null'); }
    catch (_) { submitted = true; }
    let proposal = copy(state.proposal), dirty = Boolean(submitted), revision = 0;
    if (oneClick && valid(submitted) && codes.length === submitted.order.length &&
        codes.every(code => submitted.order.includes(code))) proposal = copy(submitted);
    let anchor = null;
    let calculatedRevision = -1, calculationTimer = null, storageCompatible = true;
    const bars = document.getElementById('weight-bars');
    const status = document.getElementById('weight-status');
    const preview = document.getElementById('weight-preview');
    const accepted = form.elements.accept_derived_weights;
    const saveButtons = [...form.querySelectorAll('[data-save-configuration]')];
    const percent = value => (value / 100).toFixed(2) + '%';
    function clearConsistency() {
        if (!vaultCards) return;
        const consistency = document.getElementById('weight-consistency');
        consistency.textContent = proposal ? 'Calculating...' : 'Not calculated';
        consistency.dataset.result = '';
    }
    const canSave = () => {
        if (!proposal) {
            saveButtons.forEach(button => { button.disabled = true; });
            return;
        }
        if (oneClick) {
            const saved = state.approvableProposal;
            const matchesDraft = saved && saved.order.join('|') === proposal.order.join('|') &&
                proposal.order.every(code => saved.weights[code] === proposal.weights[code]);
            saveButtons.forEach(button => { button.disabled = calculatedRevision !== revision ||
                (button.value === 'LOCKED' && (!storageCompatible || state.requireSavedProposal && !matchesDraft)); });
            return;
        }
        const blocked = dirty && !(accepted.checked && form.elements.weight_review.value);
        saveButtons.forEach(button => {
            button.disabled = blocked || (!dirty && !state.hasSavedWeights && button.value === 'LOCKED');
        });
    };
    function invalidate(message) {
        revision++;
        dirty = true;
        clearConsistency();
        if (form.elements.weight_review) form.elements.weight_review.value = '';
        form.elements.slider_proposal.value = proposal ? JSON.stringify(proposal) : '';
        if (!proposal) {
            clearTimeout(calculationTimer);
            calculatedRevision = -1;
            preview.hidden = true;
            document.getElementById('preview-weights').disabled = true;
            status.textContent = 'Move the top slider to choose your weights. No proposal has been saved.';
            canSave();
            return;
        }
        if (oneClick) {
            preview.hidden = true;
            status.textContent = 'Calculating Saaty-compatible weights...';
            canSave();
            clearTimeout(calculationTimer);
            calculationTimer = setTimeout(calculate, 300);
            return;
        }
        form.elements.weight_review.value = '';
        accepted.checked = false;
        preview.hidden = true;
        status.textContent = message || 'Unsaved proposal. Review the resulting AHP weights before saving.';
        canSave();
    }
    const controls = {};
    for (const code of codes) {
        const row = document.createElement('div');
        row.className = 'weight-row';
        row.dataset.criterion = code;
        const heading = document.createElement('div'); heading.className = 'weight-row-heading';
        const label = document.createElement('label'); label.htmlFor = 'weight-' + code;
        label.textContent = displayNames[code] + ' (' + code + ')';
        const output = document.createElement('output'); output.id = 'weight-output-' + code;
        output.htmlFor = 'weight-' + code;
        const order = document.createElement('div'); order.className = 'weight-order';
        const buttons = [-1, 1].map(direction => {
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'btn btn-outline-secondary btn-sm';
            button.textContent = direction === -1 ? '\u2191' : '\u2193';
            button.setAttribute('aria-label', 'Move ' + state.names[code] + (direction === -1 ? ' higher' : ' lower') + ' in priority');
            button.addEventListener('click', () => {
                if (proposal) proposal = reorder(proposal, proposal.order.indexOf(code), direction);
                else {
                    const index = pendingOrder.indexOf(code), other = index + direction;
                    if (other < 0 || other >= pendingOrder.length) return;
                    [pendingOrder[index], pendingOrder[other]] = [pendingOrder[other], pendingOrder[index]];
                }
                anchor = null; invalidate('Priority changed in this proposal. Review and authorize it before use.'); render();
                if (button.disabled) controls[code].buttons[direction === -1 ? 1 : 0].focus();
                else button.focus();
            });
            order.appendChild(button); return button;
        });
        const range = document.createElement('input');
        range.type = 'range'; range.id = 'weight-' + code; range.className = 'weight-range'; range.step = '0.01';
        range.setAttribute('aria-describedby', 'weight-rules weight-output-' + code);
        const hint = document.createElement('p'); hint.className = 'small text-secondary mb-0';
        hint.id = 'weight-hint-' + code;
        range.setAttribute('aria-describedby', 'weight-rules weight-output-' + code + ' ' + hint.id);
        const source = document.createElement('span'); source.className = 'weight-source';
        const scale = document.createElement('div'); scale.className = 'weight-scale'; scale.setAttribute('aria-hidden', 'true');
        const minimum = document.createElement('span'); minimum.textContent = '0%';
        const maximum = document.createElement('span'); maximum.textContent = '100%';
        scale.append(minimum, maximum);
        range.addEventListener('pointerdown', () => { anchor = copy(proposal); });
        range.addEventListener('change', () => { anchor = null; });
        range.addEventListener('input', () => {
            proposal = proposal ? cascade(anchor || proposal, proposal.order.indexOf(code), Number(range.value) * 100) :
                begin(pendingOrder, Number(range.value) * 100);
            document.getElementById('preview-weights').disabled = false;
            invalidate(); render(false);
        });
        if (vaultCards) {
            const footer = document.createElement('div'); footer.className = 'weight-row-footer';
            heading.append(label, output); footer.append(hint, source, order);
            row.append(heading, range, footer);
        } else {
            heading.append(label, output, order); row.append(heading, range, scale, hint);
        }
        controls[code] = {row, range, output, buttons, hint, source};
    }
    function render(reorderRows = true) {
        const order = proposal ? proposal.order : pendingOrder;
        order.forEach((code, index) => {
            const control = controls[code];
            control.source.textContent = index === 0 ? 'Highest priority' : state.sourceLabels?.[code] || '';
            if (reorderRows) bars.appendChild(control.row);
            control.range.min = 0; control.range.max = 100;
            if (vaultCards) control.range.style.setProperty('--weight-fill', proposal ? percent(proposal.weights[code]) : '0%');
            control.buttons[0].disabled = index === 0; control.buttons[1].disabled = index === order.length - 1;
            if (!proposal) {
                control.range.value = 0;
                control.range.disabled = index !== 0;
                control.range.setAttribute('aria-valuetext', 'Weight not selected');
                control.output.textContent = 'Not set';
                control.hint.textContent = index === 0 ? 'Move this slider to start. The remaining weight is shared below it.' :
                    index === order.length - 1 ? 'Receives the remaining weight automatically. Move it higher for direct adjustment.' :
                    'Choose the top weight first, then adjust this slider.';
                if (vaultCards) control.hint.textContent = index === 0 ? 'Move this slider to start' :
                    index === order.length - 1 ? 'Auto remaining' : 'Choose the top weight first';
                return;
            }
            const allowed = choices(proposal, index);
            control.range.value = proposal.weights[code] / 100; control.range.disabled = index === proposal.order.length - 1;
            control.range.setAttribute('aria-valuetext', percent(proposal.weights[code]) + (index === proposal.order.length - 1 ? ', remaining weight' : ''));
            control.output.textContent = percent(proposal.weights[code]);
            control.hint.textContent = index === proposal.order.length - 1 ? 'Automatically receives the remaining weight. Move it higher in priority to adjust it.' :
                allowed[0] === allowed[allowed.length - 1] ?
                    'At its priority limit. Adjust an earlier weight or move this criterion higher to make room.' :
                    'Adjustable from ' + percent(allowed[0]) + ' to ' + percent(allowed[allowed.length - 1]) + '. ' +
                    'Increasing ' + code + ' decreases ' + proposal.order.slice(index + 1).join(', ') +
                    '; decreasing it increases them.';
            if (vaultCards) control.hint.textContent = index === order.length - 1 ? 'Auto remaining' :
                'Range: ' + percent(allowed[0]) + ' – ' + percent(allowed[allowed.length - 1]);
        });
        if (!initial) document.getElementById('weight-origin').textContent = proposal ?
            (state.requireSavedProposal ? 'Unsaved weights selected with the sliders. Review all four before saving a draft.' :
                'Review the calculated weights, then approve the configuration.') : state.startingLabel;
        if (!proposal) {
            document.getElementById('weight-summary').textContent = 'Start with ' + pendingOrder[0] + '. Once selected, the combined total stays at 100.00%.';
            document.getElementById('weight-total').textContent = 'Not set';
            return;
        }
        document.getElementById('weight-summary').textContent = proposal.order.map(code => code + ' ' + percent(proposal.weights[code])).join(' \u00b7 ');
        document.getElementById('weight-total').textContent = percent(Object.values(proposal.weights).reduce((a, b) => a + b, 0));
    }
    document.getElementById('reset-weights').addEventListener('click', () => {
        proposal = copy(initial); pendingOrder = [...codes]; anchor = null; revision++; dirty = false;
        if (oneClick) {
            invalidate();
            render();
            return;
        }
        form.elements.slider_proposal.value = ''; form.elements.weight_review.value = '';
        accepted.checked = false; preview.hidden = true;
        status.textContent = 'Reset to the starting proposal. Saved configuration unchanged.';
        render(); canSave();
    });
    async function calculate() {
        clearTimeout(calculationTimer);
        if (!proposal) return;
        if (!oneClick) invalidate('Checking the AHP result...');
        else {
            calculatedRevision = -1;
            preview.hidden = true;
            clearConsistency();
            status.textContent = 'Calculating Saaty-compatible weights...';
            canSave();
        }
        const currentRevision = revision, button = document.getElementById('preview-weights');
        const finish = window.ActionFeedback?.start(button, {button, label: 'Calculating weights…'});
        button.disabled = true;
        const body = new FormData();
        body.set('csrfmiddlewaretoken', form.elements.csrfmiddlewaretoken.value);
        body.set('action', 'PREVIEW_WEIGHTS');
        body.set('expected', form.elements.expected.value);
        body.set('slider_proposal', JSON.stringify(proposal));
        if (form.elements.calculation_method) body.set('calculation_method', form.elements.calculation_method.value);
        try {
            // Named action buttons shadow HTMLFormElement.action in browsers.
            const response = await fetch(form.getAttribute('action') || window.location.href,
                {method: 'POST', body, credentials: 'same-origin'});
            if (!response.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Unable to review weights. Reload the page and try again.');
            }
            const data = await response.json();
            if (currentRevision !== revision) return;
            if (!response.ok) throw new Error((data.errors || ['Unable to review weights. Reload and try again.']).join(' '));
            const tbody = document.getElementById('weight-preview-rows'); tbody.replaceChildren();
            data.rows.forEach(item => {
                const row = document.createElement('tr');
                const name = vaultCards && displayNames[item.code] ? displayNames[item.code] + ' (' + item.code + ')' : item.name;
                [name, item.target + '%', item.actual + '%'].forEach((value, index) => {
                    const cell = document.createElement(index === 0 ? 'th' : 'td');
                    if (index === 0) cell.setAttribute('scope', 'row');
                    cell.textContent = value; row.appendChild(cell);
                }); tbody.appendChild(row);
            });
            document.getElementById('weight-adjustment').hidden = !data.rows.some(item => item.target !== item.actual);
            const consistency = document.getElementById('weight-consistency');
            if (consistency && data.consistency) consistency.textContent =
                'Consistency: ' + data.consistency.result + ' · CR ' + data.consistency.CR +
                ' · RI ' + data.consistency.RI + ' · ' + data.consistency.criteria_count + ' criteria.';
            if (vaultCards && consistency && data.consistency) {
                const cr = Number(data.consistency.CR);
                consistency.textContent = 'Consistency: ' + data.consistency.result + ' (CR ' +
                    (Number.isFinite(cr) ? cr.toFixed(4) : data.consistency.CR) + ')';
                consistency.dataset.result = data.consistency.result;
                consistency.title = 'CR ' + data.consistency.CR + ' · RI ' + data.consistency.RI +
                    ' · ' + data.consistency.criteria_count + ' criteria';
            }
            if (form.elements.weight_review) form.elements.weight_review.value = data.token;
            calculatedRevision = currentRevision;
            storageCompatible = !(data.storage_errors || []).length;
            preview.hidden = false;
            status.textContent = oneClick ? (state.requireSavedProposal ?
                'Calculated weights are ready. Save changes as a weight draft, then review and approve the unchanged draft.' :
                'Calculated weights are ready. Review them below, then approve to save this version.') :
                'Review the resulting percentages below. Accepting them does not save or authorize the configuration.';
            if (!storageCompatible) status.textContent = data.storage_errors.join(' ');
            else if (vaultCards && oneClick && !state.requireSavedProposal)
                status.textContent = 'Review the calculated weights and add an audit note before approval.';
        } catch (error) {
            if (currentRevision === revision) {
                status.textContent = error.message;
                if (vaultCards) document.getElementById('weight-consistency').textContent = 'Review needed';
            }
        } finally { finish?.(); button.disabled = !proposal; canSave(); }
    }
    document.getElementById('preview-weights').addEventListener('click', calculate);
    if (!oneClick) {
        accepted.checked = false; accepted.addEventListener('change', canSave);
    }
    document.getElementById('weight-origin').textContent = state.startingLabel || (state.startingFromSaved ?
        'Starting from the saved calculated weights. Adjustments create a new proposal.' :
        'Equal weights are a starting proposal only. Review and authorization are still required.');
    if (dirty || oneClick) invalidate('Review this submitted proposal again before saving.');
    document.getElementById('weight-editor').hidden = false;
    render(); canSave();
    });
})(typeof globalThis !== 'undefined' ? globalThis : this);
