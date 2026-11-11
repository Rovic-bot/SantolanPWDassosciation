'use strict';
WorkspacePage.run(({on, fetch}) => {
  const root = document.querySelector('[data-announcement-programs]');
  if (!root) return;
  const host = root.querySelector('[data-results-grid]');
  const feedback = root.querySelector('[data-announcement-feedback]');
  let selected = host.querySelector('[data-announcement-results]').dataset.selectedId;
  function select(id, announce = false, reveal = false) {
    const panels = [...host.querySelectorAll('[data-announcement-panel]')];
    selected = panels.some(panel => panel.dataset.announcementPanel === id) ? id : panels[0]?.dataset.announcementPanel || '';
    panels.forEach(panel => { panel.hidden = panel.dataset.announcementPanel !== selected; });
    host.querySelectorAll('[data-announcement-row]').forEach(row => {
      const active = row.dataset.announcementRow === selected;
      row.dataset.selected = String(active);
      const link = row.querySelector('[data-announcement-select]');
      link.removeAttribute('aria-current'); link.setAttribute('role', 'button');
      link.setAttribute('aria-pressed', String(active)); link.setAttribute('aria-controls', 'announcement-program-overview');
    });
    const panel = panels.find(panel => !panel.hidden);
    const rail = host.querySelector('.selection-analysis');
    rail.scrollTop = 0;
    if (announce && panel) feedback.textContent = `Showing ${panel.querySelector('h2').textContent} publication overview.`;
    if (reveal && matchMedia('(max-width: 1199px)').matches) {
      rail.focus({preventScroll: true}); rail.scrollIntoView({block: 'start', behavior: 'instant'});
    }
  }
  on(root, 'click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('[data-announcement-select]');
    if (!link) return;
    event.preventDefault(); select(link.dataset.announcementSelect, true, true);
    const url = new URL(location.href); url.searchParams.set('selected', selected); url.hash = '';
    history.pushState({}, '', url.pathname + url.search);
  });
  on(root, 'keydown', event => {
    const link = event.target.closest('[data-announcement-select]');
    if (link && event.key === ' ') { event.preventDefault(); if (!event.repeat) link.click(); }
  });
  on(window, 'popstate', () => select(new URL(location.href).searchParams.get('selected') || ''));
  let refreshVersion = 0;
  on(document, 'announcement-results:changed', async () => {
    const version = ++refreshVersion;
    const url = new URL(root.dataset.listUrl, location.href);
    url.search = location.search; url.searchParams.set('selected', selected);
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error();
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (version !== refreshVersion) return;
      const updated = parsed.querySelector('[data-announcement-results]');
      if (!updated) throw new Error();
      const scrollTop = host.querySelector('.selection-analysis').scrollTop;
      const focusedAction = document.activeElement?.closest('[data-results-preview]')?.href;
      host.replaceChildren(document.importNode(updated, true)); select(selected);
      host.querySelector('.selection-analysis').scrollTop = scrollTop;
      if (focusedAction) [...host.querySelectorAll('[data-results-preview]')].find(link => link.href === focusedAction)?.focus({preventScroll: true});
    } catch (_) {
      feedback.classList.remove('visually-hidden'); feedback.textContent = 'Reload this page to update the publication overview.';
    }
  });
  select(selected);
});
