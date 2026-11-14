'use strict';
WorkspacePage.run(({on, fetch, setTimeout}) => {
  if (!document.querySelector('.ewaf-page')) return;
  document.documentElement.classList.add('ewaf-enhanced');
  let timer, controller, saving = false, bulkNativePending = false;
  let loadedUrl = new URL(location.href);

  function updateBulkSelection() {
    const form = document.getElementById('bulk-assistance-form');
    if (!form) return false;
    const boxes = [...document.querySelectorAll('[data-bulk-application]:not(:disabled)')];
    const checked = boxes.filter(box => box.checked);
    const slots = checked.reduce((total, box) => total + Number(box.dataset.slotNeeded || 0), 0);
    const remaining = Number(form.dataset.remainingSlots);
    const all = document.querySelector('[data-bulk-select-all]');
    if (all) {
      all.checked = boxes.length > 0 && checked.length === boxes.length;
      all.indeterminate = checked.length > 0 && checked.length < boxes.length;
      all.disabled = !boxes.length || form.dataset.bulkAvailable !== 'true';
    }
    form.querySelector('[data-bulk-count]').textContent = String(checked.length);
    const valid = checked.length > 0 && slots <= remaining && form.dataset.bulkAvailable === 'true';
    form.querySelector('[data-bulk-submit]').disabled = !valid || saving;
    form.querySelector('[data-bulk-feedback]').textContent = slots > remaining
      ? `These applicants need ${slots} new slots, but only ${remaining} are available. Uncheck applicants before selecting.` : '';
    for (const detail of document.querySelectorAll('[data-bulk-tie]')) {
      const box = boxes.find(item => item.value === detail.dataset.bulkTie);
      const selected = Boolean(box?.checked);
      detail.querySelector('textarea').required = selected;
      if (selected) detail.open = true;
    }
    return valid;
  }

  function replaceWorkspace(parsed, url) {
    for (const selector of ['#ranking-body', '#ranking-state', '#readiness', '#workspace-notice', '#unranked-applicants', '#applicant-panels']) {
      const live = document.querySelector(selector), fresh = parsed.querySelector(selector);
      if (live && fresh) live.replaceWith(fresh);
    }
    loadedUrl = new URL(url);
    for (const name of ['q', 'decision']) {
      const live = document.querySelector(`#ranking-filters [name="${name}"]`);
      const fresh = parsed.querySelector(`#ranking-filters [name="${name}"]`);
      if (live && fresh) live.value = fresh.value;
    }
    const body = document.getElementById('ranking-body');
    const countLabel = document.querySelector('[data-ranking-count]');
    if (body && countLabel) {
      const {count, total} = body.dataset;
      countLabel.textContent = count === total ? `${total} applicants` : `${count} of ${total} applicants`;
    }
    updateBulkSelection();
  }

  function replaceSelection(parsed, url, focusOnSubmit) {
    const panel = document.getElementById('readiness');
    const next = parsed.getElementById('readiness');
    const focus = panel.contains(document.activeElement) || (focusOnSubmit && document.activeElement === document.body);
    const focusId = document.activeElement.id;
    const position = {x: window.scrollX, y: window.scrollY, top: panel.scrollTop, left: panel.scrollLeft};
    const table = document.querySelector('#ranking-body .table-responsive');
    const tableLeft = table?.scrollLeft || 0;
    const decision = panel.querySelector('.ewaf-selection-decision');
    const nextDecision = next.querySelector('.ewaf-selection-decision');
    // A shorter selected state must not clamp the panel's existing scroll position.
    if (decision && nextDecision) nextDecision.style.minHeight = `${decision.getBoundingClientRect().height}px`;
    for (const detail of panel.querySelectorAll('details[open]')) {
      const summary = detail.querySelector('summary')?.textContent;
      [...next.querySelectorAll('details')].find(item => item.querySelector('summary')?.textContent === summary)?.setAttribute('open', '');
    }
    replaceWorkspace(parsed, url);
    const current = document.getElementById('readiness');
    if (focus) (document.getElementById(focusId) || current.querySelector('.ewaf-selection-decision button') || current).focus({preventScroll: true});
    current.scrollTo({left: position.left, top: position.top, behavior: 'instant'});
    const currentTable = document.querySelector('#ranking-body .table-responsive');
    if (currentTable) currentTable.scrollLeft = tableLeft;
    window.scrollTo({left: position.x, top: position.y, behavior: 'instant'});
  }

  async function saveSelection(form) {
    if (saving) return;
    saving = true;
    clearTimeout(timer);
    controller?.abort();
    const body = new FormData(form);
    const finish = window.ActionFeedback?.start(form, {label: 'Saving selection…'});
    const url = new URL(location.href);
    url.searchParams.set('run', body.get('decision-run_id'));
    url.searchParams.set('review', body.get('decision-application_id'));
    const postUrl = new URL(form.getAttribute('action') || location.href, location.href);
    for (const name of ['q', 'decision', 'page', 'applicants_page']) {
      if (url.searchParams.has(name)) postUrl.searchParams.set(name, url.searchParams.get(name));
    }
    const controls = [...document.querySelectorAll('#readiness button:not(:disabled), #ranking-filters input:not(:disabled), #ranking-filters button:not(:disabled), #ranking-filters select:not(:disabled), #generate-ranking-form button:not(:disabled)')];
    const panel = document.getElementById('readiness');
    const focusOnSubmit = panel.contains(document.activeElement);
    controls.forEach(control => { control.disabled = true; });
    panel.setAttribute('aria-busy', 'true');
    const announce = message => {
      const feedback = document.querySelector('#readiness [data-selection-feedback]');
      if (feedback) feedback.textContent = message;
    };
    announce('Saving selection…');
    try {
      let response = await fetch(postUrl, {method: 'POST', body, credentials: 'same-origin', cache: 'no-store'});
      let parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      // The ordinary POST redirect omits list filters. Re-read that same view
      // when needed, never replay the decision POST.
      if (response.ok && response.redirected && ['q', 'decision', 'page', 'applicants_page'].some(name => url.searchParams.has(name))) {
        response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
        parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      }
      if (!response.ok || parsed.getElementById('readiness')?.dataset.application !== body.get('decision-application_id')
          || parsed.getElementById('applicant-panels')?.dataset.run !== body.get('decision-run_id')) throw new Error('Selection response unavailable');
      const error = parsed.querySelector('#ranking-state .alert-danger')?.textContent.trim();
      replaceSelection(parsed, url, focusOnSubmit);
      announce(error || 'Selection updated.');
    } catch (error) {
      if (error.name !== 'AbortError') announce('Could not confirm the change. Reload this workspace to check the selection before trying again.');
    } finally {
      finish?.();
      saving = false;
      controls.forEach(control => { if (control.isConnected) control.disabled = false; });
      document.getElementById('readiness')?.removeAttribute('aria-busy');
      updateBulkSelection();
    }
  }

  function workspaceKey(url) {
    const key = new URL(url);
    key.hash = '';
    key.searchParams.delete('review');
    const run = document.getElementById('applicant-panels')?.dataset.run;
    if (run && !key.searchParams.has('run')) key.searchParams.set('run', run);
    key.searchParams.sort();
    return key.href;
  }

  function finishSelection(url, focusPanel, historyMode) {
    if (historyMode === 'push' && url.href !== location.href) history.pushState(null, '', url);
    if (historyMode === 'replace') history.replaceState(null, '', url);
    if (focusPanel) {
      const panel = document.getElementById('readiness');
      panel.focus({preventScroll: true});
      if (matchMedia('(max-width: 1100px)').matches) panel.scrollIntoView({block: 'start', behavior: 'instant'});
    }
  }

  function showLoadedApplicant(url, {focusPanel = false, historyMode = 'replace'} = {}) {
    if (saving) return false;
    const panels = document.getElementById('applicant-panels');
    if (!panels || workspaceKey(url) !== workspaceKey(loadedUrl)) return false;
    const id = url.searchParams.get('review') || panels.dataset.defaultApplicant;
    const template = [...panels.querySelectorAll('template[data-applicant-panel]')]
      .find(item => item.dataset.applicantPanel === id);
    if (!template) return false;
    clearTimeout(timer);
    controller?.abort();
    document.getElementById('readiness').replaceWith(template.content.firstElementChild.cloneNode(true));
    document.querySelectorAll('tr[data-applicant]').forEach(row => {
      const selected = row.dataset.applicant === id;
      row.classList.toggle('is-selected', selected);
      const link = row.querySelector('[data-applicant-open]');
      if (selected) link?.setAttribute('aria-current', 'true');
      else link?.removeAttribute('aria-current');
    });
    const status = document.getElementById('ranking-filter-status');
    if (status) status.textContent = 'Applicant inputs updated.';
    finishSelection(url, focusPanel, historyMode);
    return true;
  }

  async function updateWorkspace(url, {focusPanel = false, historyMode = 'replace'} = {}) {
    if (saving) return;
    clearTimeout(timer);
    controller?.abort();
    controller = new AbortController();
    const signal = controller.signal;
    const status = document.getElementById('ranking-filter-status');
    const panel = document.getElementById('readiness');
    if (status) status.textContent = 'Updating applicants...';
    panel?.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal});
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (signal.aborted) return;
      if (!response.ok || !parsed.getElementById('readiness')) {
        location.assign(url);
        return;
      }
      replaceWorkspace(parsed, url);
      if (status) status.textContent = 'Applicant inputs updated. Scores and ranks use the complete saved pool.';
      finishSelection(url, focusPanel, historyMode);
    } catch (error) {
      if (error.name !== 'AbortError') location.assign(url);
    } finally {
      if (controller?.signal === signal) document.getElementById('readiness')?.removeAttribute('aria-busy');
    }
  }

  on(document, 'click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    let link = event.target.closest('[data-applicant-open]');
    if (!link && !event.target.closest('a,button,input,select,textarea,[data-bulk-tie]')) {
      link = event.target.closest('tr[data-applicant]')?.querySelector('[data-applicant-open]');
    }
    if (!link || !document.getElementById('readiness')) return;
    event.preventDefault();
    if (saving) return;
    const url = new URL(link.href), options = {focusPanel: true, historyMode: 'push'};
    if (!showLoadedApplicant(url, options)) updateWorkspace(url, options);
  });
  on(document, 'change', event => {
    if (event.target.matches('[data-bulk-select-all]')) {
      document.querySelectorAll('[data-bulk-application]:not(:disabled)').forEach(box => { box.checked = event.target.checked; });
      updateBulkSelection();
    } else if (event.target.matches('[data-bulk-application]')) updateBulkSelection();
    const select = event.target.closest('[data-auto-submit]');
    if (select) select.form.requestSubmit();
  });
  on(document, 'submit', event => {
    if (event.target.matches('#bulk-assistance-form')) {
      if (saving || !updateBulkSelection()) {
        event.preventDefault();
        return;
      }
      clearTimeout(timer);
      controller?.abort();
      saving = true;
      bulkNativePending = true;
      event.target.setAttribute('aria-busy', 'true');
      event.target.querySelector('[data-bulk-submit]').textContent = 'Selecting checked applicants…';
      return; // One ordinary POST; never retry a selection automatically.
    }
    const form = event.target.closest('#readiness .selection-form, #readiness .selection-unselect-form, #readiness .selection-review-form');
    if (!form) return;
    event.preventDefault();
    saveSelection(form);
  });
  on(window, 'pageshow', () => {
    if (!bulkNativePending) return;
    saving = bulkNativePending = false;
    const form = document.getElementById('bulk-assistance-form');
    form?.removeAttribute('aria-busy');
    const button = form?.querySelector('[data-bulk-submit]');
    if (button) button.textContent = 'Select checked for assistance';
    updateBulkSelection();
  });
  on(window, 'popstate', () => {
    if (!document.getElementById('readiness')) return;
    const url = new URL(location.href), options = {historyMode: null};
    if (!showLoadedApplicant(url, options)) updateWorkspace(url, options);
  });

  updateBulkSelection();

  const filter = document.getElementById('ranking-filters');
  if (!filter) return;
  function filterResults() {
    const url = new URL(location.href);
    url.search = new URLSearchParams(new FormData(filter)).toString();
    url.hash = 'results';
    updateWorkspace(url);
  }
  on(filter, 'submit', event => { event.preventDefault(); filterResults(); });
  on(filter.querySelector('[name=q]'), 'input', () => {
    clearTimeout(timer);
    controller?.abort();
    timer = setTimeout(filterResults, 400);
  });
  on(filter.querySelector('[name=decision]'), 'change', filterResults);
});
