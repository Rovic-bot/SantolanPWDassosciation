WorkspacePage.run(({on, fetch}) => {
/* Enhance existing private HTML routes; calculation stays in the protected service. */
(() => {
  'use strict';
  const root = document.querySelector('[data-ewaf-selection]');
  if (!root || !window.fetch || !window.AbortController) return;
  const filters = root.querySelector('[data-selection-filters]');
  const feedback = root.querySelector('[data-selection-feedback]');
  const search = filters.elements.namedItem('q');
  let selected = null, timer, controller, revision = 0, composing = false, generating = false;
  filters.querySelector('[data-filter-submit]').hidden = true;

  function select(id, announce = true, reveal = false) {
    const panels = [...root.querySelectorAll('[data-program-panel]')];
    if (!panels.some(panel => panel.dataset.programPanel === String(id))) return;
    selected = String(id);
    panels.forEach(panel => { panel.hidden = panel.dataset.programPanel !== selected; });
    root.querySelectorAll('[data-program-row]').forEach(row => {
      const active = row.dataset.programRow === selected;
      row.dataset.selected = String(active);
      const link = row.querySelector('[data-select-program]');
      link.setAttribute('role', 'button');
      link.setAttribute('aria-pressed', String(active));
      link.setAttribute('aria-controls', 'selected-program-panel');
      link.removeAttribute('aria-current');
    });
    const panel = panels.find(item => !item.hidden);
    const rail = root.querySelector('.selection-analysis');
    rail.scrollTop = 0;
    const loading = loadPanel(panel);
    if (announce) feedback.textContent = `Selected ${panel.querySelector('h2').textContent}.`;
    if (reveal && matchMedia('(max-width: 1199px)').matches) {
      rail.focus({preventScroll: true});
      rail.scrollIntoView({block: 'start', behavior: 'instant'});
    }
    return loading;
  }
  async function loadPanel(panel) {
    if (!panel?.dataset.panelUrl || panel.dataset.loading) return;
    panel.dataset.loading = 'true';
    panel.setAttribute('aria-busy', 'true');
    const status = panel.querySelector('[data-panel-status]');
    status.textContent = 'Checking the applicant pool and saved ranking…';
    panel.querySelector('[data-retry-panel]').hidden = true;
    try {
      const response = await fetch(panel.dataset.panelUrl, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('Panel unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = parsed.querySelector('[data-program-panel]');
      if (!next || next.dataset.programPanel !== panel.dataset.programPanel) throw new Error('Session unavailable');
      if (!panel.isConnected) return;
      next.hidden = next.dataset.programPanel !== selected;
      panel.replaceWith(document.importNode(next, true));
    } catch (_) {
      status.textContent = 'Readiness checks could not be loaded. Retry or open the scoring workspace.';
      panel.querySelector('[data-retry-panel]').hidden = false;
    } finally {
      delete panel.dataset.loading;
      panel.removeAttribute('aria-busy');
    }
  }
  function initialize(preferred) {
    const results = root.querySelector('[data-selection-results]');
    const ids = [...results.querySelectorAll('[data-program-row]')].map(row => row.dataset.programRow);
    selected = ids.includes(preferred) ? preferred : results.dataset.selectedId;
    if (selected) return select(selected, false);
  }
  function filterPrograms(updateHistory = true) {
    const query = search.value.trim().toLocaleLowerCase();
    const state = filters.elements.namedItem('configuration').value;
    const visible = [];
    root.querySelectorAll('[data-program-row]').forEach(row => {
      row.hidden = !(row.dataset.search.toLocaleLowerCase().includes(query) && (!state || row.dataset.state === state));
      if (!row.hidden) visible.push(row.dataset.programRow);
    });
    if (visible.length) select(visible.includes(selected) ? selected : visible[0], false);
    else {
      selected = null;
      root.querySelectorAll('[data-program-panel]').forEach(panel => { panel.hidden = true; });
    }
    root.querySelector('[data-selection-empty]').hidden = visible.length > 0;
    root.querySelector('[data-analysis-empty]').hidden = visible.length > 0;
    root.querySelector('.selection-columns').hidden = visible.length === 0;
    root.querySelector('[data-selection-count]').textContent = visible.length;
    root.querySelector('.selection-count > span').textContent = visible.length === 1 ? 'program' : 'programs';
    feedback.textContent = `${visible.length} matching programs.`;
    if (updateHistory) {
      const url = urlForFilters();
      history.replaceState({}, '', url.pathname + url.search);
    }
  }
  function cancel() {
    clearTimeout(timer); controller?.abort(); revision++;
    root.querySelector('[data-selection-results]').removeAttribute('aria-busy');
  }
  function urlForFilters() {
    const url = new URL(filters.action);
    url.search = new URLSearchParams(new FormData(filters)).toString();
    if (selected) url.searchParams.set('selected', selected);
    return url;
  }
  async function refresh(url, historyMode = 'replace', preferred = selected) {
    cancel();
    const request = revision;
    controller = new AbortController();
    root.querySelector('[data-selection-results]').setAttribute('aria-busy', 'true');
    feedback.textContent = 'Updating programs…';
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', cache: 'no-store'});
      if (request !== revision) return false;
      if (response.redirected && new URL(response.url).pathname.includes('/login/')) { location.assign(response.url); return false; }
      if (!response.ok) throw new Error('Unable to load programs');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (request !== revision) return false;
      const next = parsed.querySelector('[data-selection-results]');
      if (!next) throw new Error('Unable to load programs');
      root.querySelector('[data-selection-results]').replaceWith(document.importNode(next, true));
      root.querySelector('[data-selection-count]').textContent = next.dataset.resultCount;
      root.querySelector('.selection-count > span').textContent = Number(next.dataset.resultCount) === 1 ? 'program' : 'programs';
      await initialize(preferred);
      filterPrograms(false);
      if (selected) url.searchParams.set('selected', selected); else url.searchParams.delete('selected');
      if (historyMode !== 'none') history[historyMode === 'push' ? 'pushState' : 'replaceState']({}, '', url.pathname + url.search);
      filters.querySelector('[data-filter-submit]').hidden = true;
      feedback.textContent = `${next.dataset.resultCount} matching programs.`;
      return true;
    } catch (error) {
      if (error.name !== 'AbortError' && request === revision) {
        feedback.textContent = 'Could not update programs. Press Enter or Filter programs to try again.';
        filters.querySelector('[data-filter-submit]').hidden = false;
      }
      return false;
    } finally {
      if (request === revision) root.querySelector('[data-selection-results]').removeAttribute('aria-busy');
    }
  }
  async function generate(form) {
    if (generating || form.querySelector('button').disabled) return;
    cancel();
    const body = new FormData(form), url = urlForFilters(), program = form.dataset.program;
    const submit = form.querySelector('button');
    const finish = window.ActionFeedback?.start(form, {button: submit, label: 'Generating ranking…',
      message: 'Checking applicants and calculating EWAF scores. The saved ranking stays visible until the new run is confirmed.'});
    generating = true;
    submit.disabled = true;
    [...filters.elements].forEach(control => { control.disabled = true; });
    feedback.textContent = 'Checking the complete applicant pool and generating its ranking…';
    const reloadHint = () => {
      const reload = document.createElement('a');
      reload.href = location.href; reload.className = 'selection-text-link';
      reload.textContent = 'Reload ranking status';
      feedback.append(' ', reload);
    };
    try {
      const response = await fetch(form.getAttribute('action'), {method: 'POST', body, credentials: 'same-origin', cache: 'no-store'});
      if (response.redirected && new URL(response.url).pathname.includes('/login/')) { location.assign(response.url); return; }
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (!response.ok || !response.redirected || !parsed.querySelector('.ewaf-ranking-table')) {
        const error = parsed.querySelector('.alert-danger');
        const message = error?.textContent.trim() || 'The ranking result could not be confirmed. Check the latest status before trying again.';
        const loaded = await refresh(url, 'replace', program);
        feedback.textContent = message;
        if (!loaded) reloadHint();
        return;
      }
      const loaded = await refresh(url, 'replace', program);
      feedback.textContent = loaded ? 'Ranking saved. The leading applicants are ready to review.' : 'Ranking saved. Reload the workspace to see the preview.';
      if (loaded) {
        await loadPanel(root.querySelector('[data-program-panel]:not([hidden])'));
        const rail = root.querySelector('.selection-analysis');
        const preview = rail.querySelector('[data-program-panel]:not([hidden]) [data-ranking-preview]');
        if (preview) { preview.tabIndex = -1; preview.focus({preventScroll: true}); preview.scrollIntoView({block: 'nearest', behavior: 'instant'}); }
      }
    } catch (_) {
      feedback.textContent = 'Could not confirm the result. Reload this workspace before trying again.';
      reloadHint();
      // A lost response may still have saved a run; never repeat the POST automatically.
    } finally {
      finish?.();
      generating = false;
      [...filters.elements].forEach(control => { control.disabled = false; });
    }
  }
  search.addEventListener('input', event => {
    cancel();
    if (!composing && !event.isComposing && !generating) filterPrograms();
  });
  search.addEventListener('compositionstart', () => { composing = true; cancel(); });
  search.addEventListener('compositionend', () => { composing = false; if (!generating) filterPrograms(); });
  filters.addEventListener('change', event => { if (event.target.matches('select') && !generating) filterPrograms(); });
  root.addEventListener('submit', event => {
    if (event.target === filters) { event.preventDefault(); if (!generating) filterPrograms(); }
    if (event.target.matches('[data-generate-ranking]')) { event.preventDefault(); generate(event.target); }
  });
  root.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const retry = event.target.closest('[data-retry-panel]');
    if (retry) { loadPanel(retry.closest('[data-program-panel]')); return; }
    const link = event.target.closest('[data-select-program], [data-selection-reset], [data-selection-page]');
    if (!link) return;
    event.preventDefault();
    if (generating) return;
    if (link.matches('[data-select-program]')) {
      cancel(); select(link.dataset.selectProgram, true, true);
      const url = new URL(location.href); url.searchParams.set('selected', selected);
      history.replaceState({}, '', url.pathname + url.search);
    } else if (link.matches('[data-selection-reset]')) {
      filters.reset(); search.value = ''; filters.elements.namedItem('configuration').value = '';
      filterPrograms(); search.focus({preventScroll: true});
    } else refresh(new URL(link.href), 'push');
  });
  root.addEventListener('keydown', event => {
    const link = event.target.closest('[data-select-program]');
    if (link && event.key === ' ') { event.preventDefault(); if (!event.repeat && !generating) link.click(); }
  });
  on(window, 'popstate', () => {
    if (generating) return;
    const url = new URL(location.href);
    search.value = url.searchParams.get('q') || '';
    filters.elements.namedItem('configuration').value = url.searchParams.get('configuration') || '';
    selected = url.searchParams.get('selected');
    filterPrograms(false);
  });
  initialize(root.querySelector('[data-selection-results]').dataset.selectedId);
})();

});
