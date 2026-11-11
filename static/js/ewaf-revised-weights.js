/* Revised draft controls only. All values are integer basis points; no cascade. */
(function () {
    'use strict';
    const codes = ['HI', 'SI', 'ES', 'PA'];
    const minima = [2640, 1948, 1407, 1223];
    const maxima = [6255, 3421, 2360, 1774];
    const defaults = [3421, 2360, 1774, 1223];
    function remainder(values) {
        if (values.length !== 4 || values.some((v, i) => !Number.isInteger(v) || v < minima[i] || v > maxima[i])) {
            return {valid: false, message: 'Use the displayed ranges in 0.01% steps.'};
        }
        const hm = 10000 - values.reduce((sum, value) => sum + value, 0);
        return {valid: hm >= 0, hm, message: hm < 0 ? 'This combination exceeds 100%. Reduce a proposed weight.' :
            hm === 0 ? 'HM is zero: allowed for exploration only, never for an AHP configuration.' :
            'Draft proposal only. Other weights have not changed; official scoring remains blocked.'};
    }
    if (typeof module !== 'undefined') module.exports = {remainder, minima, maxima, defaults};
    if (typeof document === 'undefined') return;
    const form = document.getElementById('revised-weight-form');
    if (!form) return;
    const numbers = codes.map(code => form.querySelector('[data-proposal-number="' + code + '"]'));
    const sliders = codes.map(code => form.querySelector('[data-proposal-range="' + code + '"]'));
    const mode = document.getElementById('id_mode');
    const feedback = document.getElementById('weight-feedback');
    const percent = value => (value / 100).toFixed(2);
    const parse = input => /^\d+(?:\.\d{1,2})?$/.test(input.value) ? Math.round(Number(input.value) * 100) : NaN;
    function update(changed) {
        const values = numbers.map(parse);
        const state = remainder(values);
        if (changed) mode.value = 'DRAFT_SENSITIVITY';
        document.getElementById('hm-weight').textContent = Number.isInteger(state.hm) ? percent(state.hm) : '—';
        document.getElementById('total-weight').textContent = state.valid ? '100.00' : 'Invalid';
        feedback.textContent = state.message;
        feedback.classList.toggle('text-danger', !state.valid);
        numbers.forEach((input, i) => {
            const others = values.reduce((sum, value, j) => sum + (i === j ? 0 : value), 0);
            const effectiveMax = Number.isFinite(others) ? Math.max(minima[i], Math.min(maxima[i], 10000 - others)) : maxima[i];
            sliders[i].max = percent(effectiveMax);
            if (Number.isFinite(values[i])) sliders[i].value = percent(values[i]);
            // Number entries remain visible when invalid; never silently redistribute or clamp them.
            input.setCustomValidity(state.valid ? '' : state.message);
        });
        form.querySelectorAll('[data-preview-submit]').forEach(button => { button.disabled = !state.valid; });
    }
    numbers.forEach(input => input.addEventListener('input', () => update(true)));
    sliders.forEach((slider, i) => slider.addEventListener('input', () => {
        numbers[i].value = slider.value;
        update(true);
    }));
    document.getElementById('reset-example').addEventListener('click', () => {
        numbers.forEach((input, i) => { input.value = percent(defaults[i]); });
        mode.value = 'DOCUMENT_EXAMPLE';
        update(false);
    });
    update(false);
}());
