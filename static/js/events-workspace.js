WorkspacePage.run(({on, addEventListener, fetch, setTimeout, ResizeObserver}) => {
/* Protected HTML filtering and a compact, independently scrollable agenda. */
(() => {
  'use strict';
  const root = document.querySelector('[data-event-workspace]');
  const form = root?.querySelector('[data-event-filters]');
  if (!form || !window.fetch || !window.AbortController) return;
  const search = form.elements.namedItem('q'), feedback = form.querySelector('[data-event-feedback]');
  let timer, controller, revision = 0, composing = false;
  form.querySelector('[data-event-submit]').hidden = true;
  let agendaObserver;
  function sizeAgenda() {
    agendaObserver?.disconnect();
    const list = root.querySelector('.event-agenda-list');
    if (!list) return;
    const cards = [...list.querySelectorAll('.event-agenda-card')].slice(0, 3);
    if (cards.length < 3) { list.style.maxHeight = 'none'; return; }
    const resize = () => {
      const first = cards[0].getBoundingClientRect(), last = cards[2].getBoundingClientRect();
      const style = getComputedStyle(list);
      const height = Math.ceil(last.bottom - first.top + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom));
      list.style.setProperty('--agenda-visible-height', `${height}px`);
    };
    if (window.ResizeObserver) {
      agendaObserver = new ResizeObserver(resize);
      cards.forEach(card => agendaObserver.observe(card));
    }
    resize();
  }
  sizeAgenda();
  function cancel() {
    clearTimeout(timer); controller?.abort(); revision++;
    root.querySelector('[data-event-results]').removeAttribute('aria-busy');
  }
  function filterUrl() {
    const url = new URL(form.action);
    url.search = new URLSearchParams(new FormData(form)).toString();
    return url;
  }
  function syncForm(url) {
    for (const control of form.querySelectorAll('input, select')) {
      control.value = url.searchParams.get(control.name) || (control.name === 'period' ? 'upcoming' : '');
    }
  }
  async function refresh(url, mode = 'replace', focus = '') {
    cancel();
    const request = revision;
    controller = new AbortController();
    root.querySelector('[data-event-results]').setAttribute('aria-busy', 'true');
    feedback.textContent = 'Updating events…';
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', cache: 'no-store'});
      if (request !== revision) return;
      if (response.redirected && new URL(response.url).pathname.includes('/login/')) { location.assign(response.url); return; }
      if (!response.ok) throw new Error('Events unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (request !== revision) return;
      const next = parsed.querySelector('[data-event-results]');
      if (!next) throw new Error('Events unavailable');
      root.querySelector('[data-event-results]').replaceWith(document.importNode(next, true));
      const count = Number(next.dataset.resultCount);
      root.querySelector('[data-event-count]').textContent = new Intl.NumberFormat().format(count);
      root.querySelector('[data-event-count-label]').textContent = `matching event${count === 1 ? '' : 's'}`;
      for (const name of ['month', 'day', 'period']) form.elements.namedItem(name).value = next.dataset[name] || '';
      form.querySelector('[data-event-submit]').hidden = true;
      feedback.textContent = '';
      if (mode !== 'none') history[mode === 'push' ? 'pushState' : 'replaceState']({}, '', url.pathname + url.search);
      sizeAgenda();
      if (focus) {
        const target = root.querySelector(focus);
        target.tabIndex = -1; target.focus({preventScroll: true});
        if (focus === '.event-agenda') target.scrollIntoView({block: 'start', behavior: 'instant'});
      }
    } catch (error) {
      if (error.name !== 'AbortError' && request === revision) {
        feedback.textContent = 'Could not update events. Change a filter or press Enter to try again.';
        form.querySelector('[data-event-submit]').hidden = false;
      }
    } finally {
      if (request === revision) root.querySelector('[data-event-results]').removeAttribute('aria-busy');
    }
  }
  search.addEventListener('input', event => {
    cancel();
    if (!composing && !event.isComposing) timer = setTimeout(() => refresh(filterUrl()), 300);
  });
  search.addEventListener('compositionstart', () => { composing = true; cancel(); });
  search.addEventListener('compositionend', () => { composing = false; cancel(); timer = setTimeout(() => refresh(filterUrl()), 300); });
  form.addEventListener('change', event => {
    if (event.target.matches('select')) {
      if (event.target.name === 'period') form.elements.namedItem('day').value = '';
      refresh(filterUrl());
    }
  });
  form.addEventListener('submit', event => { event.preventDefault(); refresh(filterUrl()); });
  root.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (event.target.closest('[data-event-reset]')) {
      event.preventDefault(); cancel();
      const url = new URL(form.action); syncForm(url);
      refresh(url); search.focus({preventScroll: true}); return;
    }
    const link = event.target.closest('[data-event-link], [data-event-page]');
    if (link) {
      event.preventDefault();
      const url = new URL(link.href);
      const focus = link.matches('[data-event-page]') || url.searchParams.has('day') ? '.event-agenda' : '.event-mini-calendar h2';
      refresh(url, 'push', focus); return;
    }
    if (event.target.closest('a[href]')) cancel();
  });
  addEventListener('popstate', () => { const url = new URL(location.href); syncForm(url); refresh(url, 'none'); });
  addEventListener('pagehide', cancel);
  on(document, 'program-details:changed', () => refresh(new URL(location.href), 'none'));
  on(document, 'click', event => {
    const link = event.target.closest('a[href]');
    if (link && !root.contains(link) && event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey) cancel();
  });
})();

});
