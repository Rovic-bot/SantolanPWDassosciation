/* Local filtering/copying of rows already authorized for public display. */
(() => {
    'use strict';
    const initialize = () => document.querySelectorAll('[data-public-result] [data-result-tools]').forEach(control => { control.hidden = false; });
    initialize();
    document.addEventListener('public:results-updated', initialize);
    document.addEventListener('public:details-loaded', initialize);
    const updateRows = result => {
        const query = (result.querySelector('[data-result-search]')?.value || '').trim().toUpperCase();
        const onlySelected = result.querySelector('[data-result-filter="selected"]')?.getAttribute('aria-pressed') === 'true';
        const filterRows = (selector, selectedOnly) => {
            const rows = [...result.querySelectorAll(selector)];
            let visible = 0;
            rows.forEach(row => {
                const reference = row.querySelector('[data-result-reference]').textContent.trim().toUpperCase();
                // Digits entered alone mean the reference ending, not the
                // program code/year shared by every applicant in this list.
                const matches = /^\d+$/.test(query) ? reference.endsWith(query) : reference.includes(query);
                row.hidden = !matches || (selectedOnly && row.dataset.resultSelected !== 'true');
                if (!row.hidden) visible++;
            });
            return {visible, total: rows.length};
        };
        const applicants = filterRows('[data-result-applicant]', onlySelected);
        const recipients = filterRows('[data-result-recipient]', false);
        const applicantEmpty = result.querySelector('[data-result-filter-empty]');
        const recipientEmpty = result.querySelector('[data-result-recipient-empty]');
        if (applicantEmpty) applicantEmpty.hidden = applicants.visible !== 0;
        if (recipientEmpty) recipientEmpty.hidden = recipients.visible !== 0;
        const label = `Showing ${applicants.visible} of ${applicants.total} published applications${onlySelected ? ' — selected only' : ''}.`;
        if (result.querySelector('[data-result-filter]')) result.querySelector('[data-result-applicant-count]').textContent = label;
        const recipientLabel = `Showing ${recipients.visible} of ${recipients.total} published recipients.`;
        const recipientCount = result.querySelector('[data-result-recipient-count]');
        recipientCount.hidden = !query;
        recipientCount.textContent = recipientLabel;
        result.querySelector('[data-result-status]').textContent = `${label} ${recipientLabel}`;
    };
    document.addEventListener('input', event => {
        if (event.target.matches('[data-result-search]')) updateRows(event.target.closest('[data-public-result]'));
    });
    document.addEventListener('click', async event => {
        const filter = event.target.closest('[data-result-filter]');
        const copy = event.target.closest('[data-result-copy]');
        const result = (filter || copy)?.closest('[data-public-result]');
        if (!result) return;
        const feedback = result.querySelector('[data-result-status]');
        if (filter) {
            result.querySelectorAll('[data-result-filter]').forEach(button => button.setAttribute('aria-pressed', String(button === filter)));
            updateRows(result);
            return;
        }
        const reference = copy.closest('td').querySelector('[data-result-reference]').textContent.trim();
        try {
            await navigator.clipboard.writeText(reference);
            if (result.isConnected) feedback.textContent = `Copied published reference ${reference}.`;
        } catch (_) {
            if (result.isConnected) feedback.textContent = 'Copy is unavailable. Select and copy the reference shown in the table.';
        }
    });
})();
