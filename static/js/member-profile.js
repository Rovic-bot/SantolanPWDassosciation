(() => {
    const noMiddle = document.querySelector('[name=no_middle_name]');
    const middle = document.querySelector('[name=middle_name]');
    const suffix = document.querySelector('[name=suffix]');
    const other = document.querySelector('[name=suffix_other]');
    if (!noMiddle || !middle || !suffix || !other) return;
    const structured = Boolean(document.querySelector('[name=first_name]')?.required);
    const update = () => {
        middle.disabled = noMiddle.checked;
        if (noMiddle.checked) middle.value = '';
        middle.required = structured && !noMiddle.checked;
        const custom = suffix.value === 'other';
        other.disabled = !custom;
        other.required = custom;
        other.closest('[data-profile-field]').hidden = !custom;
    };
    noMiddle.addEventListener('change', update);
    suffix.addEventListener('change', update);
    update();
})();
