/* Aggregate review counts only. Scoped fetches/timers stop on workspace navigation. */
WorkspacePage.run(({on, fetch, setTimeout}) => {
  const badges = [...document.querySelectorAll('[data-review-count]')];
  const source = document.querySelector('[data-review-count-url]');
  if (!badges.length || !source) return;
  let busy = false, stopped = false;

  function show(data, requestedIds = null) {
    for (const badge of document.querySelectorAll('[data-review-count]')) {
      // A filter can replace the cards while an earlier count request is in flight.
      if (badge.dataset.reviewCount === 'program' && requestedIds && !requestedIds.has(badge.dataset.programCountId)) continue;
      const count = badge.dataset.reviewCount === 'program'
        ? (data.program_cards?.[badge.dataset.programCountId] ?? 0) : data[badge.dataset.reviewCount];
      if (!Number.isSafeInteger(count) || count < 0) continue;
      const label = `${count} application${count === 1 ? '' : 's'} awaiting review`;
      badge.textContent = count;
      badge.hidden = count === 0;
      badge.setAttribute('aria-label', label);
      badge.title = label;
      const summary = badge.closest('summary');
      if (summary) {
        const current = summary.closest('details').dataset.current === 'true' ? ', current module' : '';
        summary.setAttribute('aria-label', summary.querySelector('[data-module-label]').textContent + current + (count ? `, ${label}` : ''));
      }
    }
  }

  async function update() {
    if (busy || stopped || document.hidden || !source.isConnected) return;
    busy = true;
    try {
      const url = new URL(source.dataset.reviewCountUrl, window.location.href);
      const ids = new Set([...document.querySelectorAll('[data-program-count-id]')].map(badge => badge.dataset.programCountId));
      if (ids.size) url.searchParams.set('programs', [...ids].join(','));
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}});
      if (!source.isConnected) return;
      if ([401, 403].includes(response.status) || response.redirected) {
        stopped = true;
        show({membership: 0, association: 0, pdao: 0, programs: 0, program_cards: {}});
        return;
      }
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const data = await response.json();
      if (source.isConnected) show(data, ids);
    } catch (_) { /* Keep the last known counts during transient network failures. */ }
    finally { busy = false; }
  }

  async function tick() {
    if (stopped || !source.isConnected) return;
    await update();
    if (!stopped && source.isConnected) setTimeout(tick, 15000);
  }
  on(document, 'visibilitychange', update);
  on(window, 'online', update);
  on(document, 'record-details:closed', update);
  setTimeout(tick, 100);
});
