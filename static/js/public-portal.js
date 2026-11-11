/* Public presentation enhancements only: no application data or workflow changes. */
(() => {
  'use strict';
  if (!document.body.classList.contains('public-portal')) return;

  // The whole guidance card toggles its native disclosure. Keep action links,
  // text selection and summary keyboard/click behavior independent.
  document.addEventListener('click', event => {
    const card = event.target.closest('[data-guidance-card]');
    if (!card || event.defaultPrevented || event.target.closest('summary, a, button, input, select, textarea, label, [contenteditable], [data-portal-field]')) return;
    if (window.getSelection()?.toString().trim()) return;
    const summary = card.querySelector('details > summary');
    if (summary) { summary.focus({preventScroll: true}); summary.click(); }
  });

  const imageFallback = image => {
    if (!image?.matches?.('.public-program-artwork img')) return;
    image.hidden = true;
    image.parentElement.querySelector('.public-program-initials').hidden = false;
  };
  document.addEventListener('error', event => imageFallback(event.target), true);
  const checkArtwork = () => document.querySelectorAll('.public-program-artwork img').forEach(image => {
    if (image.complete && !image.naturalWidth) imageFallback(image);
  });
  checkArtwork();
  document.addEventListener('public:results-updated', checkArtwork);

  const switcher = document.querySelector('[data-service-switch]');
  let selectService;
  if (switcher) {
    const tabs = [...switcher.querySelectorAll('[data-service-tab]')];
    const panels = [...switcher.querySelectorAll('[data-service-panel]')];
    const tablist = switcher.querySelector('.portal-service-selector');
    tablist.setAttribute('role', 'tablist');
    selectService = (id, focus = false) => {
      tabs.forEach(tab => {
        const selected = tab.dataset.serviceTab === id;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focus) tab.focus();
      });
      panels.forEach(panel => { panel.hidden = panel.id !== id; });
    };
    tabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', tab.dataset.serviceTab);
      const panel = document.getElementById(tab.dataset.serviceTab);
      panel.setAttribute('role', 'tabpanel');
      panel.setAttribute('aria-labelledby', tab.id);
      panel.tabIndex = 0;
      tab.addEventListener('click', event => {
        event.preventDefault();
        selectService(panel.id);
        history.replaceState(null, '', '#' + panel.id);
      });
      tab.addEventListener('keydown', event => {
        if (event.key === ' ') {
          event.preventDefault();
          tab.click();
          return;
        }
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next === undefined) return;
        event.preventDefault();
        selectService(tabs[next].dataset.serviceTab, true);
        history.replaceState(null, '', tabs[next].getAttribute('href'));
      });
    });
    selectService(panels[0].id);
  }

  const contactDestination = document.querySelector('[data-contact-destination]')?.dataset.contactDestination;
  if (contactDestination && location.hash === '#contact') {
    location.replace(contactDestination);
    return;
  }

  const revealAnchor = (hash, moveFocus = false) => {
    if (!hash || hash === '#') return;
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
    const target = document.getElementById(id);
    if (!target) return;
    document.dispatchEvent(new CustomEvent('public:reveal', { detail: { target } }));
    const service = target.closest('[data-service-panel]');
    if (service && selectService) selectService(service.id);
    let parent = target;
    while (parent) {
      if (parent.tagName === 'DETAILS') parent.open = true;
      parent = parent.parentElement;
    }
    if (moveFocus) {
      const destination = target.tagName === 'DETAILS' ? target.querySelector('summary') : target;
      if (!destination.matches('a,button,input,select,textarea,summary,[tabindex]')) destination.tabIndex = -1;
      destination.focus({ preventScroll: true });
      target.scrollIntoView({ block: 'start', behavior: 'instant' });
    }
  };
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('data-service-tab')) return;
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin && url.pathname === location.pathname && url.search === location.search && url.hash) {
      revealAnchor(url.hash);
      requestAnimationFrame(() => revealAnchor(url.hash, true));
    }
  });
  window.addEventListener('hashchange', () => revealAnchor(location.hash, true));
  window.addEventListener('popstate', () => revealAnchor(location.hash, true));
  revealAnchor(location.hash);
  if (location.hash) requestAnimationFrame(() => revealAnchor(location.hash, true));

  // Include the FAQ cards in printouts, then restore the reader's disclosure state.
  const faqDropdown = document.querySelector('.public-faq-dropdown');
  if (faqDropdown) {
    let wasOpen;
    window.addEventListener('beforeprint', () => {
      if (wasOpen === undefined) wasOpen = faqDropdown.open;
      faqDropdown.open = true;
    });
    window.addEventListener('afterprint', () => {
      if (wasOpen !== undefined) faqDropdown.open = wasOpen;
      wasOpen = undefined;
    });
  }

  const views = document.querySelector('[data-view-switch]');
  const calendar = document.querySelector('[data-observance-view]');
  if (views && calendar) {
    views.hidden = false;
    views.querySelectorAll('[data-view]').forEach(button => {
      button.addEventListener('click', () => {
        calendar.dataset.observanceView = button.dataset.view;
        views.querySelectorAll('[data-view]').forEach(item => {
          item.setAttribute('aria-pressed', String(item === button));
        });
      });
    });
  }
})();
