(() => {
    'use strict';
    const inputs = [...document.querySelectorAll('[data-vault-percentage]')];
    const remainder = document.getElementById('vault-hm');
    const total = document.getElementById('vault-total');
    if (inputs.length !== 4 || !remainder || !total) return;
    const sliders = inputs.map(input => document.querySelector(
        '[data-vault-slider="' + input.dataset.vaultPercentage + '"]'));
    const save = document.querySelector('[data-save-configuration]');
    function update() {
        const values = inputs.map(input => {
            if (!/^\d+(?:\.\d{1,2})?$/.test(input.value) || !input.validity.valid) return NaN;
            return Math.round(Number(input.value) * 100);
        });
        const hm = 10000 - values.reduce((sum, value) => sum + value, 0);
        const valid = Number.isFinite(hm) && hm >= 0;
        remainder.textContent = valid ? (hm / 100).toFixed(2) : 'Invalid';
        total.textContent = valid ? 'Total: 100.00%' : 'Enter valid percentages totaling no more than 100%. HM cannot be negative.';
        sliders.forEach((slider, index) => {
            if (!slider) return;
            const input = inputs[index];
            const otherTotal = values.reduce((sum, value, i) => sum + (i === index ? 0 : value), 0);
            const maximum = Number.isFinite(otherTotal)
                ? Math.max(Math.round(Number(input.min) * 100),
                    Math.min(Math.round(Number(input.max) * 100), 10000 - otherTotal))
                : Math.round(Number(input.max) * 100);
            slider.max = (maximum / 100).toFixed(2);
            if (Number.isFinite(values[index])) slider.value = (values[index] / 100).toFixed(2);
            slider.setAttribute('aria-valuetext', Number(slider.value).toFixed(2) + '%');
        });
        if (save) save.disabled = !valid;
    }
    inputs.forEach(input => input.addEventListener('input', update));
    sliders.forEach((slider, index) => {
        if (!slider) return;
        slider.disabled = false;
        slider.addEventListener('input', () => {
            inputs[index].value = Number(slider.value).toFixed(2);
            update();
        });
    });
    update();
})();
