/* Update public GET filters and pagination without replacing the document. */
(() => {
  'use strict';
  if (!document.querySelector('[data-public-browser]') || document.querySelector('script[data-portal-page]')) return;
  const pagePath = location.pathname;
  const status = document.createElement('p');
  status.className = 'public-browse-status visually-hidden';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  document.querySelector('main').append(status);
  let controller;
  const position = () => [scrollX, scrollY];
  const remember = () => history.replaceState({ ...history.state, publicBrowse: true, scroll: position() }, '', location.href);
  remember();
  history.scrollRestoration = 'manual';
  async function update(url, root, { push = true, scroll = position(), focus = document.activeElement, lastCards = false } = {}) {
    controller?.abort();
    window.PublicMotion?.finishResults();
    const request = new AbortController();
    controller = request;
    root.setAttribute('aria-busy', 'true');
    status.className = 'public-browse-status visually-hidden';
    status.textContent = 'Updating results…';
    const focusId = focus?.id;
    const focusHref = focus?.closest('a[href]')?.getAttribute('href');
    const focusName = focus?.name;
    const listScroll = [...root.querySelectorAll('.notice-list')].map(el => el.scrollTop);
    try {
      const response = await fetch(url, { signal: request.signal, credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok || new URL(response.url).pathname !== pagePath) throw new Error('unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      const replacement = parsed.getElementById(root.id);
      if (!replacement?.hasAttribute('data-public-browser')) throw new Error('unavailable');
      if (controller !== request) return;
      const swap = () => {
        if (controller !== request || request.signal.aborted) return;
        if (push) { scroll = position(); remember(); }
        // Keep the results region tall enough that a shorter page cannot move the viewport.
        if (!replacement.hasAttribute('data-public-solo')) replacement.style.minHeight = `${root.getBoundingClientRect().height}px`;
        root.replaceWith(replacement);
        if (lastCards) replacement.querySelector('[data-swipe-pagination]')?.setAttribute('data-swipe-initial-page', 'last');
        parsed.title && (document.title = parsed.title);
        replacement.querySelectorAll('.notice-list').forEach((el, i) => { el.scrollTop = listScroll[i] || 0; });
        if (push) {
          history.pushState({ publicBrowse: true, scroll }, '', url);
        }
        let nextFocus;
        if (focusId) nextFocus = document.getElementById(focusId);
        if (!nextFocus && focusHref) nextFocus = [...replacement.querySelectorAll('a[href]')].find(el => el.getAttribute('href') === focusHref);
        if (!nextFocus && focusName) nextFocus = [...replacement.querySelectorAll('[name]')].find(el => el.name === focusName);
        nextFocus?.focus({ preventScroll: true });
        window.scrollTo({ left: scroll[0], top: scroll[1], behavior: 'instant' });
        status.textContent = 'Results updated.';
        document.dispatchEvent(new CustomEvent('public:results-updated', { detail: { root: replacement } }));
        return replacement;
      };
      if (root.dataset.publicBrowser === 'announcements' && window.PublicMotion) {
        await window.PublicMotion.changeResults(swap);
      } else {
        swap();
      }
    } catch (error) {
      if (error.name === 'AbortError' || controller !== request) return;
      status.className = 'public-browse-status alert alert-warning';
      status.textContent = 'The results could not be updated. Please try the filter again.';
    } finally {
      if (controller === request) document.querySelectorAll('[data-public-browser]').forEach(el => el.removeAttribute('aria-busy'));
    }
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    const root = link?.closest('[data-public-browser]');
    if (!root || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target || link.hasAttribute('download')) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || url.pathname !== pagePath || url.hash) return;
    event.preventDefault();
    if (url.href === location.href) {
      // Selecting the current filter also cancels a different pending filter.
      controller?.abort();
      controller = undefined;
      window.PublicMotion?.finishResults();
      root.removeAttribute('aria-busy');
      status.className = 'public-browse-status visually-hidden';
      status.textContent = '';
      return;
    }
    remember();
    update(url, root, { focus: document.getElementById(link.dataset.publicBrowseFocus) || link, lastCards: link.dataset.publicBrowseLastCards === 'true' });
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    const root = form.closest('[data-public-browser]');
    if (!root || form.method.toLowerCase() !== 'get' || event.defaultPrevented) return;
    const url = new URL(form.action || location.href);
    if (url.origin !== location.origin || url.pathname !== pagePath) return;
    event.preventDefault();
    url.search = new URLSearchParams(new FormData(form)).toString();
    if (event.submitter?.name) url.searchParams.set(event.submitter.name, event.submitter.value);
    remember();
    update(url, root);
  });
  window.addEventListener('popstate', event => {
    if (location.pathname !== pagePath || !event.state?.publicBrowse) return;
    const root = document.querySelector('[data-public-browser]');
    if (root) update(new URL(location.href), root, { push: false, scroll: event.state.scroll || [0, 0], focus: null });
  });
  window.addEventListener('pagehide', () => { controller?.abort(); });
})();
