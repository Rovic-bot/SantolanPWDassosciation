WorkspacePage.run(({on, fetch, setTimeout}) => {
/* Existing HTML GET views power full-registry search. Selection stays local. */
(() => {
  'use strict';
  const root = document.querySelector('[data-member-directory]');
  if (!root) return;
  const form = root.querySelector('[data-directory-filters]');
  const search = form.elements.namedItem('q');
  const status = form.elements.namedItem('status');
  const disability = form.elements.namedItem('disability');
  const feedback = root.querySelector('[data-directory-feedback]');
  let records = new Map();
  let selectedId = null;
  let controller = null;
  let timer = null;
  let revision = 0;

  function selectMember(id, {announce = true, reveal = false} = {}) {
    const member = records.get(String(id));
    const panel = root.querySelector('[data-member-preview]');
    if (!member || !panel) return;
    selectedId = String(id);
    root.querySelectorAll('[data-select-member]').forEach(row => {
      const selected = row.dataset.selectMember === selectedId;
      row.dataset.selected = String(selected);
      row.setAttribute('aria-pressed', String(selected));
    });
    const text = (key, value) => {
      const node = panel.querySelector(`[data-preview-${key}]`);
      if (node) node.textContent = value;
    };
    text('initials', member.initials);
    text('name', member.name);
    text('code', member.control_number);
    text('status', member.status_label);
    text('classification', member.classification);
    text('mobile', member.mobile);
    text('joined', member.joined);
    text('updated', member.updated);
    text('verification', member.verification || '');
    text('note', member.note || 'No administrative notes recorded.');
    panel.querySelector('[data-preview-status]').dataset.status = member.status;
    panel.querySelector('[data-preview-review]').hidden = !member.needs_review;
    panel.querySelector('[data-preview-verification]').hidden = !member.verification;
    panel.querySelector('[data-preview-full]').href = member.full_url;
    const edit = panel.querySelector('[data-preview-edit]');
    edit.hidden = !member.edit_url;
    if (member.edit_url) edit.href = member.edit_url;
    else edit.removeAttribute('href');
    const update = panel.querySelector('[data-preview-update]');
    if (update) {
      update.hidden = !member.update_url;
      if (member.update_url) update.href = member.update_url;
      else update.removeAttribute('href');
    }
    if (announce) panel.querySelector('[data-selection-feedback]').textContent = `Selected ${member.name}. Member preview updated.`;
    if (reveal && matchMedia('(max-width: 1279px)').matches) {
      const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.motion === 'reduce';
      panel.scrollIntoView({behavior: reduced ? 'instant' : 'smooth', block: 'start'});
      panel.querySelector('[data-preview-name]').focus({preventScroll: true});
    }
  }

  function initializeResults() {
    const data = JSON.parse(root.querySelector('#member-directory-data').textContent);
    records = new Map(data.map(member => [String(member.id), member]));
    root.querySelectorAll('[data-select-member]').forEach(row => {
      const member = records.get(row.dataset.selectMember);
      row.setAttribute('role', 'button');
      row.setAttribute('aria-controls', 'selected-member-panel');
      row.setAttribute('aria-label', `Preview ${member.name}, ${member.status_label}, ${member.control_number}`);
    });
    if (!records.has(selectedId)) selectedId = data.length ? String(data[0].id) : null;
    if (selectedId) selectMember(selectedId, {announce: false});
  }

  function filterUrl() {
    const url = new URL(form.action, location.href);
    const query = search.value.trim();
    if (query) url.searchParams.set('q', query);
    url.searchParams.set('status', status.value);
    if (disability.value) url.searchParams.set('disability', disability.value);
    return url;
  }

  async function loadResults(url, historyMode = 'replace', paging = false) {
    clearTimeout(timer);
    controller?.abort();
    controller = new AbortController();
    const requestId = ++revision;
    const results = root.querySelector('[data-directory-results]');
    results.setAttribute('aria-busy', 'true');
    feedback.textContent = 'Finding member records…';
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', cache: 'no-store'});
      if (requestId !== revision) return;
      if (response.redirected && new URL(response.url).pathname.includes('/login/')) {
        location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error('Directory unavailable');
      const documentCopy = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (requestId !== revision) return;
      const next = documentCopy.querySelector('[data-directory-results]');
      if (!next?.querySelector('#member-directory-data')) throw new Error('Directory unavailable');
      results.replaceWith(document.importNode(next, true));
      const metrics = documentCopy.querySelector('[data-directory-metrics]');
      if (metrics) root.querySelector('[data-directory-metrics]').replaceChildren(...[...metrics.childNodes].map(node => document.importNode(node, true)));
      const count = Number(next.dataset.resultCount);
      root.querySelector('[data-directory-count]').textContent = new Intl.NumberFormat().format(count);
      root.querySelector('[data-directory-count-label]').textContent = `matching record${count === 1 ? '' : 's'}`;
      form.querySelector('[data-clear-directory-filters]').hidden = !search.value && !status.value && !disability.value;
      initializeResults();
      feedback.textContent = '';
      if (historyMode !== 'none') history[historyMode === 'push' ? 'pushState' : 'replaceState']({}, '', url.pathname + url.search);
      if (paging) {
        root.querySelector('[data-directory-results]').scrollIntoView({behavior: 'instant', block: 'start'});
        root.querySelector('[data-select-member]')?.focus({preventScroll: true});
      }
    } catch (error) {
      if (error.name !== 'AbortError' && requestId === revision) feedback.textContent = 'Could not update records. Change a filter or press Enter in the search field to try again.';
    } finally {
      if (requestId === revision) root.querySelector('[data-directory-results]').removeAttribute('aria-busy');
    }
  }

  search.addEventListener('input', () => {
    clearTimeout(timer);
    controller?.abort();
    revision += 1;
    timer = setTimeout(() => loadResults(filterUrl()), 250);
  });
  status.addEventListener('change', () => loadResults(filterUrl()));
  disability.addEventListener('change', () => loadResults(filterUrl()));
  form.addEventListener('submit', event => { event.preventDefault(); loadResults(filterUrl()); });
  root.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    const clear = event.target.closest('[data-clear-directory-filters]');
    if (clear) {
      event.preventDefault();
      search.value = status.value = disability.value = '';
      loadResults(filterUrl());
      search.focus({preventScroll: true});
      return;
    }
    const page = event.target.closest('[data-directory-page]');
    if (page) {
      event.preventDefault();
      loadResults(new URL(page.href), 'push', true);
      return;
    }
    const row = event.target.closest('[data-select-member]');
    if (row) { event.preventDefault(); selectMember(row.dataset.selectMember, {reveal: true}); }
  });
  root.addEventListener('keydown', event => {
    const row = event.target.closest('[data-select-member]');
    if (row && event.key === ' ') { event.preventDefault(); if (!event.repeat) selectMember(row.dataset.selectMember, {reveal: true}); }
  });
  on(window, 'popstate', () => {
    const url = new URL(location.href);
    search.value = url.searchParams.get('q') || '';
    status.value = url.searchParams.get('status') ?? 'active';
    disability.value = url.searchParams.get('disability') || '';
    loadResults(url, 'none');
  });
  on(window, 'pagehide', () => { clearTimeout(timer); controller?.abort(); });
  initializeResults();
})();

});
