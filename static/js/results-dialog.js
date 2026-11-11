'use strict';
WorkspacePage.run(({on, fetch, cleanup}) => {
  // The protected preview and publication service remain the source of truth.
  const grid = document.querySelector('[data-results-grid]');
  const host = document.getElementById('results-dialog-host');
  const status = document.getElementById('results-dialog-status');
  if (!grid || !host || typeof HTMLDialogElement === 'undefined' ||
      typeof HTMLDialogElement.prototype.showModal !== 'function') return;
  let pending, opener, currentUrl = new URL(location.href), revision = 0, writing = false;
  const initial = host.querySelector('#program-results-dialog');
  const dialog = initial || document.createElement('dialog');
  dialog.id = 'program-results-dialog'; dialog.className = 'results-dialog';
  dialog.setAttribute('aria-labelledby', 'results-dialog-title');
  if (!initial) host.append(dialog);

  function filterPool() {
    const query = (dialog.querySelector('[data-results-search]')?.value || '').trim().toLocaleLowerCase();
    const selectedOnly = dialog.querySelector('[data-results-filter="selected"]')?.getAttribute('aria-pressed') === 'true';
    const matches = row => [...row.querySelectorAll('[data-results-name], [data-results-reference]')]
      .some(field => field.textContent.toLocaleLowerCase().includes(query));
    const applicants = [...dialog.querySelectorAll('[data-results-applicant]')];
    const selections = [...dialog.querySelectorAll('[data-results-selection]')];
    applicants.forEach(row => { row.hidden = !matches(row) || (selectedOnly && row.dataset.selected !== 'true'); });
    selections.forEach(row => { row.hidden = !matches(row); });
    const visible = applicants.filter(row => !row.hidden).length;
    const count = dialog.querySelector('[data-results-visible-count]');
    if (count) count.textContent = `Showing ${visible} of ${applicants.length} application records`;
    const emptyApplicants = dialog.querySelector('[data-results-empty="applicants"]');
    const emptySelected = dialog.querySelector('[data-results-empty="selected"]');
    if (emptyApplicants) emptyApplicants.hidden = !applicants.length || visible > 0;
    if (emptySelected) emptySelected.hidden = !selections.length || selections.some(row => !row.hidden);
  }
  function setupPool() {
    const toolbar = dialog.querySelector('[data-results-toolbar]');
    if (toolbar) { toolbar.hidden = false; filterPool(); }
    updatePublication();
  }

  function updatePublication() {
    const reason = dialog.querySelector('[data-selection-reason]');
    const publish = dialog.querySelector('[data-publish-results]');
    if (!reason || !publish) return;
    const ready = Boolean(reason.value.trim());
    reason.setCustomValidity(ready ? '' : 'Explain why these members were selected before publishing the results.');
    publish.disabled = writing || !ready || !reason.validity.valid;
    const count = dialog.querySelector('[data-selection-reason-count]');
    if (count) count.textContent = ready ? `${reason.value.length} / 2,000 characters` : 'Add a selection reason to enable Publish results.';
  }

  function placeholder(message) {
    dialog.innerHTML = '<header class="results-dialog-header"><h2 id="results-dialog-title" tabindex="-1">Publication review</h2><button type="button" class="results-dialog-close" data-results-close aria-label="Close results preview">&times;</button></header><div class="results-dialog-body"><p role="status" data-results-message></p></div>';
    dialog.querySelector('[data-results-message]').textContent = message;
  }
  function focusContent() {
    const target = dialog.querySelector('.alert') || dialog.querySelector('[aria-invalid="true"]') || dialog.querySelector('#results-dialog-title');
    if (target) {
      if (!target.matches('input, textarea, select, button, a[href]')) target.tabIndex = -1;
      target.focus({preventScroll: !target.matches('[aria-invalid="true"]')});
    }
  }
  function open() {
    document.body.classList.add('results-preview-open');
    if (!dialog.open) dialog.showModal();
    setupPool();
    focusContent();
  }
  async function load(url, form = null, submitter = null) {
    if (writing) return;
    pending?.abort();
    const request = ++revision, posting = Boolean(form);
    const options = {credentials: 'same-origin', cache: 'no-store'};
    let finish;
    if (posting) {
      writing = true;
      options.method = 'POST'; options.headers = {'X-Announcement-Dialog': '1'};
      options.body = new FormData(form);
      if (submitter?.name) options.body.append(submitter.name, submitter.value);
      finish = window.ActionFeedback?.start(form, {button: submitter});
      dialog.querySelectorAll('button[type=submit], button:not([type]), input[type=submit]').forEach(button => { button.disabled = true; });
      dialog.setAttribute('aria-busy', 'true');
    } else {
      pending = new AbortController(); options.signal = pending.signal;
      currentUrl = new URL(url); currentUrl.hash = '';
      placeholder('Loading program results…'); open();
    }
    try {
      const response = await fetch(url, options);
      if (request !== revision || !dialog.open) return;
      if (!response.ok) throw new Error(response.status === 403 ? 'You do not have permission to review or publish these results.' : 'The preview could not be loaded.');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (request !== revision || !dialog.open) return;
      const updated = parsed.querySelector('#program-results-dialog');
      if (!updated) throw new Error('Your session may have expired. Close the popup and reload the page to sign in.');
      updated.querySelectorAll('noscript').forEach(node => node.remove());
      currentUrl = new URL(response.url); currentUrl.hash = '';
      updated.querySelectorAll('a[href]').forEach(link => { link.href = new URL(link.getAttribute('href'), currentUrl).href; });
      updated.querySelectorAll('form').forEach(item => { item.action = new URL(item.getAttribute('action') || currentUrl.href, currentUrl).href; });
      dialog.replaceChildren(...[...updated.childNodes].map(node => document.importNode(node, true)));
      setupPool();
      focusContent();
    } catch (error) {
      if (error.name !== 'AbortError' && request === revision && dialog.open) {
        placeholder(posting ? 'Publication could not be confirmed. Reload the preview to check its status before trying again.' : error.message);
        const retry = document.createElement('button');
        retry.type = 'button'; retry.className = 'btn btn-outline-primary';
        retry.dataset.resultsReload = ''; retry.textContent = 'Reload preview';
        dialog.querySelector('.results-dialog-body').append(retry); focusContent();
      }
    } finally {
      finish?.();
      if (request === revision) dialog.removeAttribute('aria-busy');
      if (posting) {
        writing = false;
        updatePublication();
        // Even an uncertain response may have committed. Only refresh with GET.
        document.dispatchEvent(new CustomEvent('announcement-results:changed'));
      }
    }
  }
  on(dialog, 'click', event => {
    const filter = event.target.closest('[data-results-filter]');
    if (filter) {
      dialog.querySelectorAll('[data-results-filter]').forEach(button => button.setAttribute('aria-pressed', String(button === filter)));
      filterPool();
    }
    const historyLink = event.target.closest('[data-announcement-review] .pagination-bar a');
    if (historyLink) { event.preventDefault(); load(new URL(historyLink.href)); }
    if (event.target.closest('[data-results-close]')) dialog.close();
    if (event.target.closest('[data-results-reload]')) load(currentUrl);
    if (event.target === dialog) {
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    }
  });
  on(dialog, 'input', event => {
    if (event.target.matches('[data-results-search]')) filterPool();
    if (event.target.matches('[data-selection-reason]')) updatePublication();
  });
  on(dialog, 'submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== 'post') return;
    const url = new URL(form.getAttribute('action') || currentUrl.href, currentUrl);
    if (url.origin !== location.origin) return;
    event.preventDefault();
    if (form.id === 'generate-results-form') {
      updatePublication();
      if (!form.reportValidity()) return;
    }
    load(url, form, event.submitter);
  });
  on(dialog, 'keydown', event => {
      if (event.key !== 'Tab') return;
      const focusable = [...dialog.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
        .filter(element => element.getClientRects().length);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement;
      if (!focusable.includes(current) || (event.shiftKey && current === first) || (!event.shiftKey && current === last)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      }
  });
  on(dialog, 'close', () => {
    revision++; pending?.abort(); dialog.removeAttribute('aria-busy');
    document.body.classList.remove('results-preview-open');
    const target = opener?.isConnected ? opener : [...grid.querySelectorAll('[data-results-preview]')].find(link => link.href === opener?.href);
    (target || grid).focus({preventScroll: true});
  });
  on(grid, 'click', event => {
    const link = event.target.closest('a[data-results-preview]');
    if (!link || !grid.contains(link) || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (link.hasAttribute('data-announcement-review-trigger')) url.searchParams.set('popup', '1');
    if (url.origin !== location.origin) return;
    event.preventDefault();
    if (writing) { status.textContent = 'Publication is still being processed. Please wait.'; return; }
    status.textContent = ''; opener = link; load(url);
  });

  // Direct links and unsuccessful POSTs open the same dialog with their errors.
  if (initial) {
    opener = [...grid.querySelectorAll('[data-results-preview]')].find(link => new URL(link.href).pathname === location.pathname);
    open();
  } else if (host.dataset.reviewUrl) {
    const url = new URL(host.dataset.reviewUrl, location.href);
    opener = [...grid.querySelectorAll('[data-results-preview]')].find(link => new URL(link.href).pathname === url.pathname);
    const workspaceUrl = new URL(location.href);
    workspaceUrl.searchParams.delete('review');
    history.replaceState(history.state, '', workspaceUrl.pathname + workspaceUrl.search);
    load(url);
  }
  cleanup(() => { pending?.abort(); document.body.classList.remove('results-preview-open'); });
});
