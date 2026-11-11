WorkspacePage.run(({on, addEventListener, fetch, setTimeout}) => {
/* Search the existing protected HTML view; keep filters and focus in place. */
(() => {
  'use strict';
  const root = document.querySelector('[data-application-workspace]');
  if (!root || !window.fetch || !window.AbortController) return;
  const form = root.querySelector('[data-review-filters]');
  const search = form.elements.namedItem('q');
  const feedback = root.querySelector('[data-review-feedback]');
  let timer, controller, revision = 0, composing = false;
  form.querySelector('[data-review-submit]').hidden = true;

  let records = new Map(), selectedId = null;
  function selectProgram(id, {announce = true, reveal = false, historyUpdate = true} = {}) {
    const program = records.get(String(id)), panel = root.querySelector('[data-program-preview]');
    if (!program || !panel) return;
    selectedId = program.id;
    root.querySelectorAll('[data-program-card]').forEach(card => {
      const chosen = card.dataset.programCard === selectedId;
      card.dataset.selected = String(chosen);
      card.querySelector('[data-select-program]').setAttribute('aria-pressed', String(chosen));
    });
    const text = (name, value) => { panel.querySelector(`[data-preview-${name}]`).textContent = value; };
    for (const key of ['name','category','code','applications','available','registration','schedule','readiness','eligibility']) text(key, program[key]);
    panel.dataset.accent = program.accent;
    text('status',program.status_label);
    panel.querySelector('[data-preview-status]').dataset.status = program.status;
    text('demand',program.demand === null ? 'Capacity not set' : `${program.demand}% of ${program.capacity}-place capacity`);
    panel.querySelector('[data-preview-ring]').setAttribute('stroke-dasharray',`${program.progress} 100`);
    const list = document.createDocumentFragment();
    for (const item of program.statuses) {
      const row = document.createElement('li'), label = document.createElement('span');
      const marker = document.createElement('i'), count = document.createElement('strong');
      row.dataset.accent = item.accent; marker.setAttribute('aria-hidden','true');
      label.append(marker,document.createTextNode(item.label)); count.textContent = item.count;
      row.append(label,count); list.append(row);
    }
    panel.querySelector('[data-preview-statuses]').replaceChildren(list);
    const review = panel.querySelector('[data-preview-review]');
    review.href = program.review_url; review.hidden = !program.applications;
    panel.querySelector('[data-preview-disabled]').hidden = !!program.applications;
    panel.querySelector('[data-preview-detail]').href = program.detail_url;
    if (announce) panel.querySelector('[data-selection-feedback]').textContent = `Selected ${program.name}. ${program.applications} applications.`;
    if (historyUpdate) {
      const url = new URL(location.href); url.searchParams.set('selected',selectedId);
      history.replaceState({},'',url.pathname + url.search);
    }
    if (reveal && matchMedia('(max-width: 1279px)').matches) {
      const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.motion === 'reduce';
      panel.scrollIntoView({behavior:reduced ? 'instant' : 'smooth',block:'start'});
      panel.querySelector('[data-preview-name]').focus({preventScroll:true});
    }
  }
  function initializeResults(preferred = selectedId) {
    const rows = JSON.parse(root.querySelector('#application-program-data').textContent);
    records = new Map(rows.map(row => [row.id,row]));
    root.querySelectorAll('[data-select-program]').forEach(link => {
      link.setAttribute('role','button'); link.setAttribute('aria-controls','selected-program-panel');
    });
    selectedId = records.has(preferred) ? preferred : (root.querySelector('[data-review-results]').dataset.selectedId || null);
    if (selectedId) selectProgram(selectedId,{announce:false,historyUpdate:false});
  }

  function cancel() {
    clearTimeout(timer); controller?.abort(); revision++;
    root.querySelector('[data-review-results]').removeAttribute('aria-busy');
  }
  function filterUrl() {
    const url = new URL(form.action);
    url.search = new URLSearchParams(new FormData(form)).toString();
    return url;
  }
  async function refresh(url, mode = 'replace', paging = false) {
    cancel();
    const request = revision;
    controller = new AbortController();
    feedback.textContent = 'Updating programs…';
    root.querySelector('[data-review-results]').setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', cache: 'no-store'});
      if (request !== revision) return;
      if (response.redirected && new URL(response.url).pathname.includes('/login/')) { location.assign(response.url); return; }
      if (!response.ok) throw new Error('Programs unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (request !== revision) return;
      const next = parsed.querySelector('[data-review-results]');
      if (!next?.querySelector('#application-program-data')) throw new Error('Programs unavailable');
      root.querySelector('[data-review-results]').replaceWith(document.importNode(next, true));
      const metrics = parsed.querySelector('[data-review-metrics]');
      if (metrics) root.querySelector('[data-review-metrics]').replaceWith(document.importNode(metrics, true));
      initializeResults(mode === 'none' ? url.searchParams.get('selected') : selectedId);
      if (selectedId) url.searchParams.set('selected',selectedId); else url.searchParams.delete('selected');
      const count = Number(next.dataset.resultCount);
      root.querySelector('[data-review-count]').textContent = new Intl.NumberFormat().format(count);
      root.querySelector('[data-review-count-label]').textContent = `program${count === 1 ? '' : 's'}`;
      feedback.textContent = '';
      form.querySelector('[data-review-submit]').hidden = true;
      if (mode !== 'none') history[mode === 'push' ? 'pushState' : 'replaceState']({}, '', url.pathname + url.search);
      if (paging) {
        const board = root.querySelector('.chooser-board');
        board.tabIndex = -1;
        board.focus({preventScroll: true});
        board.scrollIntoView({block: 'start', behavior: 'instant'});
      }
    } catch (error) {
      if (error.name !== 'AbortError' && request === revision) {
        feedback.textContent = 'Could not update programs. Change a filter or press Enter to try again.';
        form.querySelector('[data-review-submit]').hidden = false;
      }
    } finally {
      if (request === revision) root.querySelector('[data-review-results]').removeAttribute('aria-busy');
    }
  }
  search.addEventListener('input', event => {
    cancel();
    if (!composing && !event.isComposing) timer = setTimeout(() => refresh(filterUrl()), 300);
  });
  search.addEventListener('compositionstart', () => { composing = true; cancel(); });
  search.addEventListener('compositionend', () => { composing = false; cancel(); timer = setTimeout(() => refresh(filterUrl()), 300); });
  form.addEventListener('change', event => { if (event.target.matches('select, input[type=checkbox]')) refresh(filterUrl()); });
  form.addEventListener('submit', event => { event.preventDefault(); refresh(filterUrl()); });
  root.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const selection = event.target.closest('[data-select-program]');
    if (selection) { event.preventDefault(); selectProgram(selection.dataset.selectProgram,{reveal:true}); return; }
    const reset = event.target.closest('[data-review-reset]');
    if (reset) {
      event.preventDefault(); cancel();
      form.querySelectorAll('input, select').forEach(control => {
        if (control.type === 'checkbox') control.checked = false;
        else control.value = control.name === 'sort' ? 'newest' : '';
      });
      refresh(filterUrl()); search.focus({preventScroll: true}); return;
    }
    const page = event.target.closest('[data-review-page]');
    if (page) { event.preventDefault(); refresh(new URL(page.href), 'push', true); return; }
    if (event.target.closest('a[href]')) cancel();
  });
  root.addEventListener('keydown', event => {
    const selection = event.target.closest('[data-select-program]');
    if (selection && event.key === ' ') { event.preventDefault(); if (!event.repeat) selectProgram(selection.dataset.selectProgram,{reveal:true}); }
  });
  addEventListener('popstate', () => {
    const url = new URL(location.href);
    for (const control of form.querySelectorAll('input, select')) {
      if (control.type === 'checkbox') control.checked = url.searchParams.get(control.name) === control.value;
      else control.value = url.searchParams.get(control.name) || (control.name === 'sort' ? 'newest' : '');
    }
    refresh(url, 'none');
  });
  addEventListener('pagehide', cancel);
  on(document, 'program-details:changed', () => refresh(new URL(location.href), 'none'));
  on(document, 'click', event => {
    const link = event.target.closest('a[href]');
    if (link && !root.contains(link) && !event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) cancel();
  });
  initializeResults(new URL(location.href).searchParams.get('selected'));
})();

});
