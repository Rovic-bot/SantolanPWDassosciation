'use strict';
WorkspacePage.run(({on, fetch, cleanup, MutationObserver}) => {
  if (!window.HTMLDialogElement) return;
  const dialog = document.createElement('dialog');
  dialog.id = 'receipt-details-popup';
  dialog.className = 'receipt-details-dialog';
  dialog.setAttribute('aria-labelledby', 'receipt-details-title');
  dialog.innerHTML = '<header><h2 id="receipt-details-title">Receipt details</h2><button type="button" data-close-receipt aria-label="Close receipt details" autofocus>×</button></header><div class="receipt-details-body"></div>';
  document.body.append(dialog);
  document.body.dataset.receiptPopups = 'true';
  function decorate() {
    document.querySelectorAll('[data-receipt-details] > summary').forEach(trigger => {
      trigger.setAttribute('role', 'button');
      trigger.setAttribute('aria-haspopup', 'dialog');
      trigger.setAttribute('aria-controls', dialog.id);
    });
  }
  new MutationObserver(decorate).observe(document.body, {childList: true, subtree: true});
  decorate();
  const body = dialog.querySelector('.receipt-details-body'), close = dialog.querySelector('[data-close-receipt]');
  let source, opener, content, writing = false;
  function restore() {
    if (source?.isConnected && content) source.append(content);
    body.replaceChildren();
    if (opener?.isConnected) opener.focus({preventScroll: true});
    source = opener = content = null;
  }
  on(document, 'click', event => {
    const summary = event.target.closest('[data-receipt-details] > summary');
    if (!summary || event.defaultPrevented) return;
    event.preventDefault();
    if (dialog.open) return;
    source = summary.parentElement; opener = summary;
    content = source.querySelector('[data-receipt-detail-content]');
    source.open = false;
    body.replaceChildren(content); dialog.showModal();
  });
  on(close, 'click', () => { if (!writing) dialog.close(); });
  on(dialog, 'cancel', event => { if (writing) event.preventDefault(); });
  on(dialog, 'close', restore);
  on(dialog, 'click', event => {
    if (event.target !== dialog || writing) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  on(dialog, 'submit', async event => {
    const form = event.target;
    if (!form.matches('[data-receipt-undo]')) return;
    event.preventDefault();
    if (writing || new URL(form.action).origin !== location.origin) return;
    const table = source.closest('[data-release-table]');
    const status = content.querySelector('[data-receipt-undo-status]');
    const button = form.querySelector('button');
    const finish = window.ActionFeedback?.start(form, {button, label: 'Undoing receipt…'});
    writing = true; button.disabled = close.disabled = true;
    status.textContent = 'Undoing receipt…';
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('Unable to undo this receipt. Check your permissions and reload the receipts.');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const fresh = page.querySelector('[data-release-table]');
      if (!fresh) throw new Error('Reload the receipts to check the result before trying again.');
      if (!dialog.isConnected) return;
      if (!table?.isConnected) { location.assign(response.url); return; }
      dialog.close(); restore();
      const replacement = document.importNode(fresh, true);
      table.replaceWith(replacement);
      document.dispatchEvent(new CustomEvent('assistance-receipts:changed'));
      document.dispatchEvent(new CustomEvent('assistance-claimant:loaded'));
      const feedback = replacement.querySelector('[role="alert"], .alert, h1');
      if (feedback) { feedback.tabIndex = -1; feedback.focus({preventScroll: true}); }
    } catch (error) {
      if (dialog.isConnected) status.textContent = error.name === 'AbortError' ? 'Reload receipts to check the result.' : 'The result could not be confirmed. Reload receipts before trying again.';
    } finally { finish?.(); writing = false; button.disabled = close.disabled = false; }
  });
  cleanup(() => { dialog.close(); restore(); dialog.remove(); delete document.body.dataset.receiptPopups; });
});
