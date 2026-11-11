'use strict';
WorkspacePage.run(({on, fetch, cleanup}) => {
  const form = document.querySelector('#activity-filters');
  const panel = document.querySelector('#activity-filter-panel');
  const toggle = document.querySelector('[data-activity-filter-toggle]');
  if (form && panel && toggle) {
    toggle.hidden = false;
    function showFilters(show) {
      panel.hidden = !show;
      toggle.setAttribute('aria-expanded', String(show));
      form.classList.toggle('activity-filters-collapsed', !show);
    }
    showFilters(!matchMedia('(max-width: 1100px)').matches || !!form.querySelector('.errorlist'));
    on(toggle, 'click', () => {
      showFilters(panel.hidden);
      if (!panel.hidden && matchMedia('(max-width: 1100px)').matches) {
        panel.querySelector('select')?.focus();
      }
    });
    const period = form.elements.namedItem('period');
    const dates = form.querySelector('[data-activity-dates]');
    function syncDates() {
      const custom = period.value === 'custom';
      dates.hidden = !custom;
      dates.querySelectorAll('input').forEach(input => { input.disabled = !custom; });
    }
    syncDates();
    on(period, 'change', syncDates);
  }

  const dialog = document.querySelector('[data-activity-dialog]');
  if (!dialog?.showModal) return;
  const body = dialog.querySelector('[data-activity-body]');
  const errorPanel = dialog.querySelector('[data-activity-error]');
  const fallback = dialog.querySelector('[data-activity-fallback]');
  const close = dialog.querySelector('[data-activity-close]');
  let opener, controller, detailURL;
  document.querySelectorAll('[data-activity-inspect]').forEach(link => link.setAttribute('aria-haspopup', 'dialog'));

  async function load() {
    controller?.abort();
    const pending = new AbortController();
    controller = pending;
    errorPanel.hidden = true;
    body.textContent = 'Loading activity details…';
    body.setAttribute('aria-busy', 'true');
    const url = new URL(detailURL);
    url.searchParams.set('dialog', '1');
    fallback.href = detailURL;
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal: pending.signal});
      if (!response.ok || response.redirected) throw new Error('unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = parsed.querySelector('[data-activity-detail]');
      if (!content) throw new Error('unavailable');
      if (pending.signal.aborted || !dialog.open) return;
      body.replaceChildren(content);
      dialog.scrollTop = 0;
    } catch (error) {
      if (pending.signal.aborted) return;
      body.replaceChildren();
      errorPanel.hidden = false;
    } finally {
      if (controller === pending) body.removeAttribute('aria-busy');
    }
  }
  on(document, 'click', event => {
    const link = event.target.closest('[data-activity-inspect]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    opener = link;
    detailURL = link.href;
    document.body.classList.add('activity-inspect-open');
    dialog.showModal();
    close.focus({preventScroll: true});
    load();
  }, {capture: true});
  on(close, 'click', () => dialog.close());
  on(dialog, 'keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]')]
      .filter(element => !element.disabled && element.tabIndex >= 0 && element.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  });
  on(dialog.querySelector('[data-activity-retry]'), 'click', load);
  on(dialog, 'click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  on(dialog, 'close', () => {
    controller?.abort();
    document.body.classList.remove('activity-inspect-open');
    opener?.focus({preventScroll: true});
  });
  cleanup(() => { controller?.abort(); document.body.classList.remove('activity-inspect-open'); });
});
