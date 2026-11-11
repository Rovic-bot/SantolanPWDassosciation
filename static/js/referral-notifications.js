/* New concern totals only; no member data is fetched or stored by the badge. */
WorkspacePage.run(({on, fetch, setTimeout}) => {
  const badges = [...document.querySelectorAll('[data-referral-new-count]')];
  if (!badges.length) return;
  const url = badges[0].dataset.countUrl;
  let busy = false, stopped = false;

  function show(count) {
    const label = `${count} new concern${count === 1 ? '' : 's'} awaiting review`;
    for (const badge of badges) {
      if (badge.textContent !== String(count)) badge.textContent = count;
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
    if (busy || stopped || document.hidden || !badges[0].isConnected) return;
    busy = true;
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}});
      if (!badges[0].isConnected) return;
      if ([401, 403].includes(response.status) || response.redirected) {
        stopped = true;
        show(0);
        return;
      }
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const data = await response.json();
      if (badges[0].isConnected && Number.isSafeInteger(data.new_count) && data.new_count >= 0) show(data.new_count);
    } catch (_) { /* Retain the last known total and retry read-only updates. */ }
    finally { busy = false; }
  }

  async function tick() {
    if (stopped || !badges[0].isConnected) return;
    await update();
    if (!stopped && badges[0].isConnected) setTimeout(tick, 3000);
  }
  on(document, 'visibilitychange', update);
  on(window, 'online', update);
  on(document, 'record-details:loaded', update);
  on(document, 'record-details:closed', update);
  setTimeout(tick, 100);
});
