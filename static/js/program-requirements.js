(() => {
    const button = document.getElementById('add-requirement');
    if (!button) return;
    button.addEventListener('click', () => {
        const total = document.getElementById('id_requirements-TOTAL_FORMS');
        const count = Number(total.value);
        if (count >= 50) return;
        const template = document.getElementById('requirement-template');
        const row = document.createElement('div');
        row.innerHTML = template.innerHTML.replaceAll('__prefix__', String(count));
        const section = row.firstElementChild;
        document.getElementById('requirement-rows').appendChild(section);
        total.value = String(count + 1);
        section.querySelector('input:not([type=hidden])').focus();
        button.disabled = count + 1 >= 50;
    });
})();
