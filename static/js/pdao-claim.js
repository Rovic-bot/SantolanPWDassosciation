WorkspacePage.run(({on}) => {
    const root = document.querySelector('[data-pdao-claim-root]');
    const form = root?.querySelector('#pdao-claim-form');
    if (!form) return;
    const options = [...root.querySelectorAll('[data-claim-select]:not(:disabled)')];
    const all = root.querySelector('[data-claim-all]');
    const confirmed = form.elements.namedItem('confirmed');
    const button = form.querySelector('[data-claim-submit]');
    root.querySelector('[data-claim-all-control]').hidden = false;
    function update() {
        const count = options.filter(option => option.checked).length;
        all.checked = options.length > 0 && count === options.length;
        all.indeterminate = count > 0 && count < options.length;
        all.disabled = options.length === 0;
        button.disabled = count === 0 || !confirmed.checked;
        form.querySelector('[data-claim-count]').textContent = `${count} selected on this page`;
    }
    on(all, 'change', () => { options.forEach(option => { option.checked = all.checked; }); update(); });
    options.forEach(option => on(option, 'change', update));
    on(confirmed, 'change', update);
    on(form, 'submit', () => { button.disabled = true; button.textContent = 'Queuing claim emails…'; });
    on(window, 'pageshow', update);
    update();
});
