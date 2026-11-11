WorkspacePage.run(({on, addEventListener, fetch, setTimeout}) => {
/* Search the existing protected HTML view; keep filters and focus in place. */
(() => {
  'use strict';
  const root = document.querySelector('[data-program-portfolio]');
  if (!root || !window.fetch || !window.AbortController) return;
  const form = root.querySelector('[data-portfolio-filters]');
  const search = form.elements.namedItem('q');
  const feedback = root.querySelector('[data-portfolio-feedback]');
  let timer, controller, revision = 0, composing = false;
  form.querySelector('[data-portfolio-submit]').hidden = true;

  function cancel() {
    clearTimeout(timer); controller?.abort(); revision++;
    root.querySelector('[data-portfolio-results]').removeAttribute('aria-busy');
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
    root.querySelector('[data-portfolio-results]').setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', cache: 'no-store'});
      if (request !== revision) return;
      if (response.redirected && new URL(response.url).pathname.includes('/login/')) { location.assign(response.url); return; }
      if (!response.ok) throw new Error('Programs unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (request !== revision) return;
      const next = parsed.querySelector('[data-portfolio-results]');
      if (!next) throw new Error('Programs unavailable');
      root.querySelector('[data-portfolio-results]').replaceWith(document.importNode(next, true));
      const metrics = parsed.querySelector('[data-portfolio-metrics]');
      if (metrics) root.querySelector('[data-portfolio-metrics]').replaceWith(document.importNode(metrics, true));
      const count = Number(next.dataset.resultCount);
      root.querySelector('[data-portfolio-count]').textContent = new Intl.NumberFormat().format(count);
      root.querySelector('[data-portfolio-count-label]').textContent = `program${count === 1 ? '' : 's'}`;
      // The default sort describes publication time while the New filter is active.
      const nextSort = parsed.querySelector('[data-portfolio-filters] [name="sort"]');
      if (nextSort) for (const option of form.elements.namedItem('sort').options) {
        const nextOption = [...nextSort.options].find(item => item.value === option.value);
        if (nextOption) option.textContent = nextOption.textContent;
      }
      feedback.textContent = '';
      form.querySelector('[data-portfolio-submit]').hidden = true;
      if (mode !== 'none') history[mode === 'push' ? 'pushState' : 'replaceState']({}, '', url.pathname + url.search);
      if (paging) {
        const board = root.querySelector('.portfolio-board');
        board.tabIndex = -1;
        board.focus({preventScroll: true});
        board.scrollIntoView({block: 'start', behavior: 'instant'});
      }
    } catch (error) {
      if (error.name !== 'AbortError' && request === revision) {
        feedback.textContent = 'Could not update programs. Change a filter or press Enter to try again.';
        form.querySelector('[data-portfolio-submit]').hidden = false;
      }
    } finally {
      if (request === revision) root.querySelector('[data-portfolio-results]').removeAttribute('aria-busy');
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
    const reset = event.target.closest('[data-portfolio-reset]');
    if (reset) {
      event.preventDefault(); cancel();
      form.querySelectorAll('input, select').forEach(control => {
        if (control.type === 'checkbox') control.checked = false;
        else control.value = control.name === 'sort' ? 'newest' : '';
      });
      refresh(filterUrl()); search.focus({preventScroll: true}); return;
    }
    const page = event.target.closest('[data-portfolio-page]');
    if (page) { event.preventDefault(); refresh(new URL(page.href), 'push', true); return; }
    if (event.target.closest('a[href]')) cancel();
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
})();

});
