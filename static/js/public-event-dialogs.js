/* Load event details through the same publication-checked public route. */
(() => {
  'use strict';
  const dialog = document.querySelector('[data-public-dialog]');
  if (!dialog || !dialog.showModal || document.querySelector('script[data-portal-page]')) return;
  const body = dialog.querySelector('[data-event-dialog-body]');
  let opener, controller;
  const markLinks = () => document.querySelectorAll('[data-public-popup]').forEach(link => link.setAttribute('aria-haspopup', 'dialog'));
  markLinks();
  document.addEventListener('public:results-updated', markLinks);
  document.addEventListener('click', async event => {
      const link = event.target.closest('[data-public-popup]');
      if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      opener = link;
      controller?.abort();
      const request = new AbortController();
      controller = request;
      dialog.classList.remove('event-poster-dialog', 'announcement-poster-dialog', 'observance-poster-dialog');
      if (link.matches('[data-event-popup]')) dialog.classList.add('event-poster-dialog');
      else if (link.closest('.observance-notice-carousel')) dialog.classList.add('observance-poster-dialog');
      else if (link.closest('#announcement-browser')) dialog.classList.add('announcement-poster-dialog');
      dialog.querySelector('[data-public-dialog-title]').textContent = link.dataset.popupLabel || 'Details';
      body.textContent = 'Loading details…';
      body.setAttribute('aria-busy', 'true');
      if (!dialog.open) dialog.showModal();
      dialog.scrollTop = 0;
      const url = new URL(link.href);
      url.searchParams.set('popup', '1');
      try {
        const response = await fetch(url, { signal: request.signal, credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) throw new Error('unavailable');
        const document = new DOMParser().parseFromString(await response.text(), 'text/html');
        const content = document.querySelector('[data-public-popup-content], [data-event-content]');
        if (!content) throw new Error('unavailable');
        if (dialog.open && controller === request) {
          dialog.classList.toggle('event-poster-dialog', content.classList.contains('event-poster-card'));
          dialog.classList.toggle('announcement-poster-dialog', content.classList.contains('announcement-poster'));
          dialog.classList.toggle('observance-poster-dialog', content.classList.contains('observance-poster'));
          body.replaceChildren(content);
          window.document.dispatchEvent(new CustomEvent('public:details-loaded'));
          window.PublicMotion?.enter(content, { distance: 8, duration: 220 });
          const artwork = content.querySelector('[data-event-poster-image], [data-announcement-poster-image]');
          if (artwork) {
            const showFallback = () => { artwork.hidden = true; };
            artwork.addEventListener('error', showFallback, { once: true });
            if (artwork.complete && !artwork.naturalWidth) showFallback();
          }
        }
      } catch (error) {
        if (error.name === 'AbortError') return;
        if (dialog.open && controller === request) {
          const message = document.createElement('p');
          message.textContent = 'These details could not be loaded. They may no longer be published.';
          const retry = document.createElement('button');
          retry.type = 'button';
          retry.className = 'btn btn-outline-primary';
          retry.textContent = 'Try again';
          retry.addEventListener('click', () => link.click(), { once: true });
          body.replaceChildren(message, retry);
        }
      } finally {
        if (controller === request) body.removeAttribute('aria-busy');
      }
  });
  dialog.addEventListener('close', () => { controller?.abort(); body.replaceChildren(); opener?.focus({ preventScroll: true }); });
  dialog.addEventListener('click', event => {
    const box = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) dialog.close();
  });
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]')].filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
})();
