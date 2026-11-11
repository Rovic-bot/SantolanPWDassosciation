'use strict';
WorkspacePage.run(({on, fetch}) => {
  const root = document.querySelector('[data-release-portfolio]');
  if (!root) return;
  const form = root.querySelector('[data-release-filters]');
  const list = root.querySelector('[data-release-rows]');
  const rows = [...list.querySelectorAll('[data-release-row]')];
  const panels = new Map([...root.querySelectorAll('[data-release-panel]')].map(panel => [panel.dataset.releasePanel, panel]));
  const rail = root.querySelector('#release-program-overview');
  const feedback = root.querySelector('[data-release-feedback]');
  const field = name => form.elements.namedItem(name);
  let selected = root.dataset.selectedId;
  let composing = false;
  root.querySelector('[data-release-submit]').hidden = true;

  function select(id, announce = false, reveal = false) {
    selected = id || '';
    panels.forEach((panel, key) => { panel.hidden = key !== selected; });
    rows.forEach(row => {
      const active = row.dataset.releaseRow === selected;
      row.dataset.selected = String(active);
      const link = row.querySelector('[data-release-select]');
      link.setAttribute('role', 'button');
      link.setAttribute('aria-pressed', String(active));
      link.setAttribute('aria-controls', 'release-program-overview');
      link.removeAttribute('aria-current');
    });
    root.querySelector('[data-release-panel-empty]').hidden = Boolean(selected);
    rail.scrollTop = 0;
    if (selected && announce) feedback.textContent = `Showing ${panels.get(selected).querySelector('h2').textContent} overview.`;
    if (selected && reveal && matchMedia('(max-width: 1199px)').matches) {
      rail.focus({preventScroll: true});
      rail.scrollIntoView({block: 'start', behavior: 'instant'});
    }
  }

  function saveUrl(mode = 'replaceState') {
    const url = new URL(location.href);
    ['q', 'assistance_type', 'status', 'registration', 'sort'].forEach(name => {
      const value = field(name).value.trim();
      if (value && !(name === 'sort' && value === 'newest')) url.searchParams.set(name, value);
      else url.searchParams.delete(name);
    });
    if (field('with_applications').checked) url.searchParams.set('with_applications', '1');
    else url.searchParams.delete('with_applications');
    if (selected) url.searchParams.set('selected', selected);
    else url.searchParams.delete('selected');
    url.searchParams.delete('page');
    history[mode]({}, '', url.pathname + url.search);
    rows.forEach(row => {
      const rowUrl = new URL(url);
      rowUrl.searchParams.set('selected', row.dataset.releaseRow);
      rowUrl.hash = 'release-program-overview';
      row.querySelector('[data-release-select]').href = rowUrl.pathname + rowUrl.search + rowUrl.hash;
    });
  }

  function filter(updateUrl = true) {
    const query = field('q').value.trim().toLocaleLowerCase();
    const matching = [];
    rows.forEach(row => {
      const matches = (!query || row.dataset.search.toLocaleLowerCase().includes(query)) &&
        ['assistance_type', 'status', 'registration'].every(name => !field(name).value || row.dataset[name === 'assistance_type' ? 'type' : name] === field(name).value) &&
        (!field('with_applications').checked || Number(row.dataset.applicants) > 0);
      row.hidden = !matches;
      if (matches) matching.push(row);
    });
    const sort = field('sort').value;
    const value = row => ['az', 'za'].includes(sort) ? row.dataset.name.toLocaleLowerCase() : row.dataset[sort === 'start' || sort === 'end' ? sort : 'created'];
    matching.sort((a, b) => {
      const av = value(a), bv = value(b);
      if (!av || !bv) return av ? -1 : bv ? 1 : a.dataset.releaseRow.localeCompare(b.dataset.releaseRow);
      const comparison = av.localeCompare(bv) || a.dataset.releaseRow.localeCompare(b.dataset.releaseRow);
      return sort === 'newest' || sort === 'za' ? -comparison : comparison;
    });
    matching.forEach(row => list.append(row));
    if (!matching.some(row => row.dataset.releaseRow === selected)) selected = matching[0]?.dataset.releaseRow || '';
    select(selected);
    root.querySelector('[data-release-count]').textContent = matching.length;
    root.querySelector('[data-release-count-label]').textContent = matching.length === 1 ? 'program' : 'programs';
    root.querySelector('[data-release-empty]').hidden = matching.length > 0;
    root.querySelector('[data-release-columns]').hidden = matching.length === 0;
    if (updateUrl) saveUrl();
  }

  on(form, 'input', event => { if (event.target === field('q') && !composing && !event.isComposing) filter(); });
  on(form, 'compositionstart', () => { composing = true; });
  on(form, 'compositionend', () => { composing = false; filter(); });
  on(form, 'change', event => { if (event.target !== field('q')) filter(); });
  on(form, 'submit', event => { event.preventDefault(); filter(); });
  on(root, 'click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('[data-release-select], [data-release-reset]');
    if (!link) return;
    event.preventDefault();
    if (link.hasAttribute('data-release-reset')) {
      ['q', 'assistance_type', 'status', 'registration'].forEach(name => { field(name).value = ''; });
      field('sort').value = 'newest'; field('with_applications').checked = false;
      filter(); field('q').focus({preventScroll: true});
    } else {
      select(link.dataset.releaseSelect, true, true);
      saveUrl('pushState');
    }
  });
  on(root, 'keydown', event => {
    const link = event.target.closest('[data-release-select]');
    if (link && event.key === ' ') { event.preventDefault(); if (!event.repeat) link.click(); }
  });
  on(window, 'popstate', () => {
    const params = new URL(location.href).searchParams;
    ['q', 'assistance_type', 'status', 'registration', 'sort'].forEach(name => { field(name).value = params.get(name) || (name === 'sort' ? 'newest' : ''); });
    field('with_applications').checked = params.get('with_applications') === '1';
    selected = params.get('selected') || '';
    filter(false);
  });
  let refreshVersion = 0;
  on(document, 'assistance-receipts:changed', async () => {
    const version = ++refreshVersion;
    try {
      const response = await fetch(location.href, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('Overview unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (version !== refreshVersion) return;
      if (!parsed.querySelector('[data-release-portfolio]')) throw new Error('Overview unavailable');
      const scrollTop = rail.scrollTop;
      const focusedAction = document.activeElement?.closest('[data-release-dialog]')?.href;
      rows.forEach(row => {
        const replacement = parsed.querySelector(`[data-release-row="${row.dataset.releaseRow}"]`);
        if (!replacement) return;
        row.replaceChildren(...[...replacement.childNodes].map(node => document.importNode(node, true)));
        row.dataset.applicants = replacement.dataset.applicants;
      });
      panels.forEach((panel, key) => {
        const replacement = parsed.querySelector(`[data-release-panel="${key}"]`);
        if (replacement) panel.replaceChildren(...[...replacement.childNodes].map(node => document.importNode(node, true)));
      });
      filter(false); rail.scrollTop = scrollTop;
      if (focusedAction) [...root.querySelectorAll('[data-release-dialog]')].find(link => link.href === focusedAction)?.focus({preventScroll: true});
    } catch (_) {
      feedback.classList.remove('visually-hidden');
      feedback.textContent = 'Reload this page to update the program overview counts.';
    }
  });
  select(selected);
});
