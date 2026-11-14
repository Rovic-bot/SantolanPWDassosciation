/* Inline PDAO editing and a private, same-page print preview. */
(() => {
  const initialize = ({on, cleanup}) => {
    const readyForm = document.querySelector('#pdao-forward-form');
    const readyDialog = document.querySelector('#pdao-ready-dialog');
    if (readyForm && readyDialog?.showModal) {
      const checkbox = readyForm.elements.namedItem('ready_confirmed');
      const fallback = readyForm.querySelector('[data-pdao-ready-fallback]');
      const confirm = readyDialog.querySelector('[data-pdao-ready-confirm]');
      let opener, confirmed = false, sending = false;
      fallback.hidden = true;
      checkbox.required = false;
      checkbox.checked = false;
      on(readyForm, 'submit', event => {
        if (sending) { event.preventDefault(); return; }
        if (confirmed) { sending = true; return; }
        event.preventDefault();
        opener = event.submitter || readyForm.querySelector('button[type=submit]');
        if (opener?.disabled) return;
        readyDialog.showModal();
        document.documentElement.classList.add('membership-dialog-open');
        readyDialog.querySelector('[autofocus]').focus();
      });
      readyDialog.querySelectorAll('[data-pdao-ready-cancel]').forEach(button =>
        on(button, 'click', () => readyDialog.close()));
      on(readyDialog, 'close', () => {
        document.documentElement.classList.remove('membership-dialog-open');
        if (!confirmed) checkbox.checked = false;
        opener?.focus({preventScroll: true});
      });
      on(confirm, 'click', () => {
        if (sending || opener?.disabled) return;
        confirmed = true; checkbox.checked = true;
        readyDialog.close();
        readyForm.requestSubmit(opener);
        // Native validation can block a submission; a later attempt must ask again.
        if (!sending) { confirmed = false; checkbox.checked = false; }
      });
      cleanup(() => {
        if (readyDialog.open) readyDialog.close();
        document.documentElement.classList.remove('membership-dialog-open');
      });
    }
    const review = document.querySelector('#pdao-manual-review');
    if (review?.dataset.pdaoNumber) {
      const decisions = review.querySelectorAll('[data-pdao-decision]');
      decisions.forEach(button => { button.disabled = true; });
      const open = review.querySelector('[data-pdao-registry-open]');
      if (open) on(open, 'click', () => {
        if (window.SantolanPrpwd?.open(review.dataset.pdaoRegistry, review.dataset.pdaoNumber,
            review.querySelector('[data-pdao-registry-feedback]'))) {
          review.querySelectorAll('[data-pdao-lookup]').forEach(input => { input.value = review.dataset.pdaoNumber; });
          decisions.forEach(button => { button.disabled = false; });
        }
      });
    }
    const form = document.querySelector('#pdao-review-form');
    const revealField = field => {
      const panel = field?.closest('[data-registration-panel]');
      if (panel) form.querySelector(`[data-registration-tab="${panel.dataset.registrationPanel}"]`)?.click();
    };
    if (form) {
      on(form, 'invalid', event => revealField(event.target), true);
      on(form, 'click', event => {
        const link = event.target.closest('.alert a[href^="#"]');
        if (link) revealField(document.getElementById(link.hash.slice(1)));
      });
      on(document, 'DOMContentLoaded', () => revealField(form.querySelector('.errorlist')?.closest('.onsite-field')));
    }
    const dialog = document.querySelector('#pdao-preview-dialog');
    if (!dialog?.showModal) return;
    const frame = dialog.querySelector('iframe'), print = dialog.querySelector('[data-pdao-preview-print]');
    const status = dialog.querySelector('[data-pdao-preview-status]');
    let opener;
    document.querySelectorAll('[data-pdao-preview-open]').forEach(link => on(link, 'click', event => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const url = new URL(link.href, location.href);
      if (url.origin !== location.origin) return;
      event.preventDefault();
      url.searchParams.set('preview', '1');
      opener = link; print.disabled = true; status.textContent = 'Loading form preview…';
      dialog.showModal(); document.documentElement.classList.add('membership-dialog-open');
      frame.src = url.href;
    }));
    on(frame, 'load', () => {
      if (!dialog.open) return;
      const ready = Boolean(frame.contentDocument?.querySelector('.pdao-sheet'));
      print.disabled = !ready;
      status.textContent = ready ? '' : 'The preview could not be loaded. Close it and reload the review to check your session.';
      if (ready) on(frame.contentDocument, 'keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); dialog.close(); }
      });
    });
    on(print, 'click', () => { if (!print.disabled) { frame.contentWindow.focus(); frame.contentWindow.print(); } });
    on(dialog.querySelector('[data-pdao-preview-close]'), 'click', () => dialog.close());
    on(dialog, 'close', () => {
      document.documentElement.classList.remove('membership-dialog-open');
      frame.src = 'about:blank'; print.disabled = true; opener?.focus({preventScroll: true});
    });
    cleanup(() => { if (dialog.open) dialog.close(); });
  };
  if (window.WorkspacePage) WorkspacePage.run(initialize);
  else initialize({on: (target, name, handler, options) => target.addEventListener(name, handler, options), cleanup: () => {}});
})();
