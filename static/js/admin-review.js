WorkspacePage.run(({on, fetch}) => {
on(document, 'DOMContentLoaded', () => {
    const showErrors = () => document.querySelectorAll('dialog[data-show-dialog]').forEach(dialog => dialog.showModal());
    showErrors();
    const markSection = () => document.querySelectorAll('.member-section-nav a').forEach(link => {
        const defaultSection = link.closest('.member-section-nav').dataset.defaultSection || '#overview';
        if (link.hash === (location.hash || defaultSection)) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
    });
    markSection();
    on(window, 'hashchange', markSection);
    const openSection = (id, updateHash = true) => {
        const target = document.getElementById(id);
        if (!target) return;
        if (target.matches('details')) target.open = true;
        for (let parent = target.parentElement; parent; parent = parent.parentElement) {
            if (parent.matches('details')) parent.open = true;
        }
        if (id === 'documents') {
            const requirements = document.getElementById('program-requirements');
            if (requirements) requirements.open = true;
        }
        document.querySelectorAll('.review-highlight').forEach(section => section.classList.remove('review-highlight'));
        target.classList.add('review-highlight');
        document.querySelectorAll('.review-check').forEach(link => {
            if (link.dataset.reviewTarget === id) link.setAttribute('aria-current', 'location');
            else link.removeAttribute('aria-current');
        });
        const heading = target.querySelector('[data-review-heading]') || target.querySelector('summary') || target;
        if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1');
        heading.focus({preventScroll:true});
        target.scrollIntoView({block:'start'});
        if (updateHash) history.replaceState(null, '', '#' + id);
        markSection();
    };
    if (location.hash && document.getElementById(location.hash.slice(1))?.matches('[data-review-section], #application-history')) {
        openSection(location.hash.slice(1), false);
    }
    on(document, 'invalid', event => {
        const section = event.target.closest('details');
        if (section) section.open = true;
    }, true);
    const decisionRemarks = (form, outcome) => {
        if (form?.id !== 'eligibility-decision-form') return true;
        const notes = form.elements.notes;
        if (!notes) return true;
        form.dataset.decisionOutcome = outcome;
        const required = outcome === 'review' || outcome === 'ineligible';
        notes.required = required;
        notes.setAttribute('aria-required', String(required));
        const label = notes.labels?.[0];
        if (label) label.textContent = required ? 'Remarks (required)' : 'Remarks (optional)';
        const message = outcome === 'review' ? 'Describe the information the applicant needs to provide.' : 'Explain why the application is ineligible.';
        notes.setCustomValidity(required && !notes.value.trim() ? message : '');
        return !required || !!notes.value.trim();
    };
    on(document, 'input', event => {
        if (event.target.name === 'notes' && event.target.form?.id === 'eligibility-decision-form') {
            decisionRemarks(event.target.form, event.target.form.dataset.decisionOutcome);
        }
    });
    on(document, 'click', async event => {
        const decision = event.target.closest('button[name="eligibility"]');
        if (decision) decisionRemarks(decision.form, decision.value);
        const reviewLink = event.target.closest('a[data-review-target]');
        if (reviewLink) {
            event.preventDefault();
            openSection(reviewLink.dataset.reviewTarget);
        }
        const opener = event.target.closest('[data-open-dialog]');
        if (opener) document.getElementById(opener.dataset.openDialog).showModal();
        const closer = event.target.closest('[data-close-dialog]');
        if (closer) closer.closest('dialog').close();
        const link = event.target.closest('.member-section-nav a');
        if (link) {
            const target = document.getElementById(link.hash.slice(1));
            if (target && target.tagName === 'DETAILS') target.open = true;
        }
        const button = event.target.closest('[data-copy-value]');
        if (button) {
            const status = document.getElementById(button.dataset.copyStatus);
            try {
                await navigator.clipboard.writeText(button.dataset.copyValue);
                status.textContent = button.dataset.copyMessage || 'Control number copied.';
            } catch (_) {
                status.textContent = 'Copy unavailable. Select and copy the identifier shown above.';
            }
        }
    });
    on(document, 'submit', async event => {
        const form = event.target;
        const documentReview = form.matches('[data-document-review-form]');
        if (!documentReview && !form.matches('[data-applicant-review-form]')) return;
        event.preventDefault();
        if (form.dataset.saving) return;
        const submit = event.submitter;
        if (submit?.name === 'eligibility' && !decisionRemarks(form, submit.value)) {
            form.reportValidity();
            return;
        }
        const data = new FormData(form);
        if (submit?.name) data.set(submit.name, submit.value);
        const finish = window.ActionFeedback?.start(form, {button: submit,
            label: submit?.name === 'eligibility' ? 'Saving decision and sending email…' : 'Saving review…'});
        form.dataset.saving = 'true';
        form.setAttribute('aria-busy', 'true');
        if (submit) submit.disabled = true;
        const error = form.querySelector('[data-review-error]');
        error.hidden = true;
        const documentId = documentReview ? form.elements.document_id.value : null;
        const sectionId = submit?.dataset.reviewTarget || form.dataset.reviewTarget;
        const openDetails = [...document.querySelectorAll('#main-content details[open][id]')].map(item => item.id);
        try {
            const response = await fetch(form.getAttribute('action'), {method:'POST', body:data, credentials:'same-origin',
                headers:{'Accept':'text/html', 'X-Requested-With':'XMLHttpRequest'}});
            if (!response.ok || new URL(response.url).pathname !== location.pathname ||
                    !response.headers.get('content-type')?.includes('text/html')) throw new Error('save');
            const page = new DOMParser().parseFromString(await response.text(), 'text/html');
            const updated = page.getElementById('main-content');
            if (!updated?.querySelector('#documents[data-document-review-saved]')) throw new Error('response');
            updated.querySelectorAll('script').forEach(script => script.remove());
            // Refresh evidence summaries and source tokens as well as the button.
            // No page navigation, automatic eligibility decision or scoring occurs.
            const position = {left:scrollX, top:scrollY};
            document.getElementById('main-content').replaceChildren(...updated.childNodes);
            openDetails.forEach(id => {
                const section = document.getElementById(id);
                if (section?.matches('details')) section.open = true;
            });
            markSection();
            if (documentReview) {
                document.querySelector('[data-member-document="' + documentId + '"]')?.focus({preventScroll:true});
                scrollTo(position);
            } else {
                const invalidSection = document.querySelector('[data-review-errors]');
                openSection(invalidSection?.id || sectionId);
            }
        } catch (_) {
            error.textContent = 'The review could not be saved. Reload the applicant page and try again.';
            error.hidden = false;
        } finally {
            finish?.();
            delete form.dataset.saving;
            form.removeAttribute('aria-busy');
            if (submit) submit.disabled = false;
        }
    });
});

});
