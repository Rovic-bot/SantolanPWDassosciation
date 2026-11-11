'use strict';
WorkspacePage.run(({on, fetch, cleanup}) => {
  const root = document.querySelector('[data-release-portfolio]');
  const dialog = document.querySelector('#assistance-releases-dialog');
  if (!root || !dialog || typeof dialog.showModal !== 'function') return;
  const content = dialog.querySelector('[data-release-dialog-content]');
  const feedback = dialog.querySelector('[data-release-dialog-status]');
  let opener, currentUrl, getController, revision = 0, writing = false;

  function failure(message) {
    feedback.textContent = message;
    const retry = document.createElement('button');
    retry.type = 'button'; retry.className = 'receipt-button';
    retry.dataset.releaseReload = ''; retry.textContent = 'Reload receipts';
    content.replaceChildren(retry); retry.focus({preventScroll: true});
  }

  async function load(url, form = null) {
    if (writing) return;
    getController?.abort();
    const request = ++revision;
    const posting = Boolean(form);
    const options = {credentials: 'same-origin', cache: 'no-store'};
    let finish;
    if (posting) {
      writing = true;
      options.method = 'POST'; options.body = new FormData(form);
      finish = window.ActionFeedback?.start(form);
      content.querySelectorAll('button').forEach(button => { button.disabled = true; });
    } else {
      getController = new AbortController(); options.signal = getController.signal;
      currentUrl = new URL(url); content.replaceChildren();
    }
    content.setAttribute('aria-busy', 'true');
    feedback.textContent = posting ? (url.toString().includes('email') ? 'Sending beneficiary email…' : 'Saving receipt change…') : 'Loading assistance releases…';
    try {
      const response = await fetch(url, options);
      if (request !== revision || !dialog.open) return;
      if (!response.ok) throw new Error(response.status === 403 ? 'You do not have permission to view or record these receipts.' : 'Unable to load assistance releases. Try reloading receipts.');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (request !== revision || !dialog.open) return;
      const table = parsed.querySelector('[data-release-table]');
      if (!table) throw new Error('Your session may have expired. Close this popup and reload the page to sign in.');
      currentUrl = new URL(response.url); currentUrl.hash = '';
      table.querySelectorAll('a[href]').forEach(link => { link.href = new URL(link.getAttribute('href'), currentUrl).href; });
      table.querySelectorAll('form').forEach(item => { item.action = new URL(item.getAttribute('action') || currentUrl.href, currentUrl).href; });
      const node = document.importNode(table, true);
      content.replaceChildren(node); content.scrollTop = 0; feedback.textContent = '';
      const isClaimant = node.classList.contains('claimant-workspace');
      dialog.querySelector('#release-dialog-title').textContent = isClaimant ? 'Record actual receipt' : 'Assistance releases';
      document.dispatchEvent(new CustomEvent('assistance-claimant:loaded'));
      const heading = isClaimant ? node.querySelector('[name="claimant_type"]') : node.querySelector('h1');
      const target = posting ? node.querySelector('.alert') || heading : heading;
      if (target) { target.tabIndex = -1; target.focus({preventScroll: true}); }
    } catch (error) {
      if (error.name !== 'AbortError' && request === revision && dialog.open) {
        failure(posting ? 'The receipt could not be confirmed. Reload receipts to check its status before trying again.' : error.message);
      }
    } finally {
      finish?.();
      if (request === revision) content.removeAttribute('aria-busy');
      if (posting) {
        writing = false;
        // Refresh counts after success or an uncertain response; never repeat a POST.
        document.dispatchEvent(new CustomEvent('assistance-receipts:changed'));
      }
    }
  }

  on(root, 'click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[data-release-dialog]');
    if (!link || new URL(link.href).origin !== location.origin) return;
    event.preventDefault();
    if (writing) return;
    opener = link;
    document.documentElement.classList.add('program-dialog-open');
    dialog.showModal(); load(link.href);
  });
  on(dialog.querySelector('[data-release-close]'), 'click', () => dialog.close());
  on(dialog, 'click', event => {
    if (event.target === dialog) {
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    }
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (event.target.closest('[data-release-reload]')) { load(currentUrl); return; }
    const link = event.target.closest('.pagination-bar a, a[data-receipt-navigation]');
    if (link && new URL(link.href).origin === location.origin) { event.preventDefault(); load(link.href); }
  });
  on(dialog, 'submit', event => {
    const form = event.target;
    if (!form.matches('.receipt-action-form')) return;
    event.preventDefault();
    const url = new URL(form.action);
    if (url.origin === location.origin) load(url, form);
  });
  on(dialog, 'close', () => {
    revision++; getController?.abort();
    document.documentElement.classList.remove('program-dialog-open');
    content.replaceChildren(); content.removeAttribute('aria-busy'); feedback.textContent = '';
    const target = opener?.isConnected ? opener : [...root.querySelectorAll('[data-release-dialog]')].find(link => link.href === opener?.href);
    target?.focus({preventScroll: true});
  });
  cleanup(() => { getController?.abort(); document.documentElement.classList.remove('program-dialog-open'); });
});
