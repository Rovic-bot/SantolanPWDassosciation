WorkspacePage.run(({on, fetch}) => {
/* Load protected member/ticket views in one accessible dialog, retaining native links. */
(() => {
  'use strict';
  const dialog = document.querySelector('#record-details-dialog');
  if (!dialog || typeof dialog.showModal !== 'function' || !window.fetch || !window.AbortController) return;
  const content = dialog.querySelector('[data-record-dialog-content]');
  const feedback = dialog.querySelector('[data-record-dialog-status]');
  const fullPage = dialog.querySelector('[data-record-full-page]');
  let opener, currentUrl, getController, revision = 0, changed = false;

  function errorState(message) {
    const panel = document.createElement('div');
    panel.className = 'record-dialog-error'; panel.setAttribute('role', 'alert'); panel.tabIndex = -1;
    const heading = document.createElement('h3'), text = document.createElement('p'), retry = document.createElement('button');
    heading.textContent = 'Record details unavailable'; text.textContent = message;
    retry.type = 'button'; retry.className = 'btn btn-outline-secondary'; retry.textContent = 'Reload details';
    retry.addEventListener('click', () => load(currentUrl));
    panel.append(heading, text, retry); content.replaceChildren(panel); panel.focus({preventScroll: true});
  }

  async function load(url, {form, submitter} = {}) {
    getController?.abort();
    const request = ++revision, writing = !!form;
    const options = {credentials: 'same-origin', cache: 'no-store'};
    let finish;
    if (writing) {
      options.method = 'POST'; options.body = new FormData(form);
      if (submitter?.name) options.body.append(submitter.name, submitter.value);
      finish = window.ActionFeedback?.start(form, {button: submitter});
      form.dataset.submitting = 'true';
      form.querySelectorAll('button, input, select, textarea').forEach(control => { control.disabled = true; });
    } else {
      getController = new AbortController(); options.signal = getController.signal;
      content.replaceChildren();
    }
    content.setAttribute('aria-busy', 'true');
    feedback.textContent = writing ? 'Saving record change…' : 'Loading record details…';
    try {
      const response = await fetch(url, options);
      if (request !== revision || !dialog.open) return;
      if (!response.ok && ![400, 409, 413].includes(response.status)) throw new Error(response.status === 403 ? 'You do not have permission to open this record.' : fullPage ? 'The record could not be loaded. Try again or use Open full page.' : 'The record could not be loaded. Try Reload details.');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (request !== revision || !dialog.open) return;
      const profile = parsed.querySelector('[data-record-content]');
      if (!profile) throw new Error(fullPage ? 'Your session may have expired. Use Open full page to sign in and continue.' : 'Your session may have expired. Close this request, sign in again, and reopen it.');
      currentUrl = new URL(response.url);
      if (fullPage) fullPage.href = currentUrl.href;
      // Relative history links and native form fallbacks must retain this record's URL.
      profile.querySelectorAll('a[href]').forEach(link => { link.href = new URL(link.getAttribute('href'), currentUrl).href; });
      profile.querySelectorAll('form').forEach(item => { item.setAttribute('action', new URL(item.getAttribute('action') || currentUrl.href, currentUrl).href); });
      const node = document.importNode(profile, true);
      content.replaceChildren(node); content.scrollTop = 0;
      const heading = node.querySelector('[role=alert], h1');
      heading.tabIndex = -1; heading.focus({preventScroll: true});
      document.dispatchEvent(new CustomEvent('record-details:loaded', {detail: {root: node}}));
    } catch (error) {
      if (error.name !== 'AbortError' && request === revision && dialog.open) {
        errorState(writing ? 'The change could not be confirmed. Reload details to check the latest status before trying again.' : error.message);
      }
    } finally {
      finish?.();
      if (request === revision) { content.removeAttribute('aria-busy'); feedback.textContent = ''; }
      // Never retry a write automatically. Refresh the underlying list even if the popup was closed.
      if (writing) { changed = true; if (!dialog.open) location.reload(); }
      if (writing) document.dispatchEvent(new CustomEvent('record-details:changed'));
    }
  }

  on(document, 'click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[data-record-dialog]');
    if (!link || link.target === '_blank') return;
    const url = new URL(link.href);
    if (url.origin !== location.origin) return;
    event.preventDefault(); opener = link; currentUrl = url;
    if (fullPage) fullPage.href = url.href;
    document.documentElement.classList.add('record-dialog-open');
    dialog.querySelector('#record-dialog-heading').textContent = link.dataset.recordDialog || 'Record details';
    dialog.showModal(); load(url);
  });
  dialog.querySelector('[data-record-dialog-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex]')]
      .filter(node => {
        const closed = node.closest('details:not([open])');
        return node.tabIndex >= 0 && !node.matches(':disabled') && node.getClientRects().length &&
          getComputedStyle(node).visibility !== 'hidden' && (!closed || closed.querySelector(':scope > summary')?.contains(node));
      });
    const target = event.shiftKey ? controls.at(-1) : controls[0];
    const boundary = event.shiftKey ? controls[0] : controls.at(-1);
    if (target && (document.activeElement === boundary || !dialog.contains(document.activeElement))) {
      event.preventDefault(); target.focus();
    }
  });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) {
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    }
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('.pagination-bar a');
    if (link && new URL(link.href).pathname === currentUrl?.pathname) { event.preventDefault(); load(new URL(link.href)); }
  });
  dialog.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.getAttribute('method')?.toLowerCase() !== 'post') return;
    // A named action button shadows HTMLFormElement.action; read the attribute.
    const url = new URL(form.getAttribute('action') || currentUrl.href, currentUrl);
    if (url.origin !== location.origin) return;
    event.preventDefault();
    if (form.dataset.submitting === 'true') return;
    load(url, {form, submitter: event.submitter});
  });
  dialog.addEventListener('close', () => {
    revision++; getController?.abort();
    document.documentElement.classList.remove('record-dialog-open');
    content.replaceChildren(); content.removeAttribute('aria-busy'); feedback.textContent = '';
    document.dispatchEvent(new CustomEvent('record-details:closed'));
    if (changed) location.reload();
    const target = opener?.isConnected ? opener : [...document.querySelectorAll('[data-record-dialog]')].find(link => link.href === opener?.href);
    (target || document.querySelector('input[type=search]'))?.focus({preventScroll: true});
  });
})();

});
