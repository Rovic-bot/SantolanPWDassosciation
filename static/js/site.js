WorkspacePage.run(({on, requestAnimationFrame}) => {
(() => {
  'use strict';
  const adminNav = document.getElementById('admin-nav');
  if (adminNav) {
    // A full page navigation recreates this independent scroll container.
    // Remember only its offset, per browser tab/account and viewport layout.
    const desktop = window.matchMedia('(min-width: 1100px)');
    const compact = adminNav.dataset.compact === 'true';
    const key = () => 'santolan.admin-navigation.' + adminNav.dataset.scrollKey + (compact ? '.compact' : '') + (desktop.matches ? '.desktop' : '.mobile');
    const sidebarToggle = document.querySelector('.workspace-sidebar-toggle');
    const sidebarKey = 'santolan.admin-navigation.' + adminNav.dataset.scrollKey + '.collapsed';
    let sidebarCollapsed = false;
    try { sidebarCollapsed = sessionStorage.getItem(sidebarKey) === 'true'; } catch (_) { /* Storage is optional. */ }
    const applySidebar = () => {
      document.body.classList.toggle('workspace-sidebar-collapsed', desktop.matches && sidebarCollapsed);
      if (sidebarToggle) {
        sidebarToggle.hidden = !desktop.matches;
        sidebarToggle.setAttribute('aria-expanded', String(!sidebarCollapsed));
        const label = sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation';
        sidebarToggle.setAttribute('aria-label', label);
        sidebarToggle.title = label;
      }
    };
    const visible = () => desktop.matches ? !sidebarCollapsed : adminNav.classList.contains('show');
    const groups = [...adminNav.querySelectorAll('details[data-group-key]')];
    const restoreGroups = () => {
      let state = {};
      try {
        const saved = JSON.parse(sessionStorage.getItem(key() + '.groups') || '{}');
        if (saved && typeof saved === 'object') state = saved;
      } catch (_) { /* All groups stay usable without storage. */ }
      groups.forEach(group => {
        group.open = group.dataset.current === 'true' || (state[group.dataset.groupKey] ?? !compact);
      });
    };
    const saveGroups = () => {
      if (!visible()) return;
      try {
        sessionStorage.setItem(key() + '.groups', JSON.stringify(Object.fromEntries(
          groups.map(group => [group.dataset.groupKey, group.open]))));
      } catch (_) { /* Disclosure works independently of storage. */ }
    };
    const save = () => {
      if (!visible() || adminNav.classList.contains('collapsing')) return;
      try { sessionStorage.setItem(key(), String(adminNav.scrollTop)); } catch (_) { /* Storage is optional. */ }
    };
    const restore = () => {
      if (!visible()) return;
      try {
        const value = Number(sessionStorage.getItem(key()));
        if (Number.isFinite(value) && value >= 0) adminNav.scrollTop = value;
      } catch (_) { /* Navigation still works when storage is unavailable. */ }
    };
    adminNav.style.scrollBehavior = 'auto';
    applySidebar();
    restoreGroups();
    restore();
    sidebarToggle?.addEventListener('click', () => {
      if (!desktop.matches) return;
      save();
      sidebarCollapsed = !sidebarCollapsed;
      try { sessionStorage.setItem(sidebarKey, String(sidebarCollapsed)); } catch (_) { /* Navigation works without storage. */ }
      applySidebar();
      restore();
    });
    groups.forEach(group => group.addEventListener('toggle', saveGroups));
    adminNav.addEventListener('scroll', save, { passive: true });
    adminNav.addEventListener('click', save);
    adminNav.addEventListener('shown.bs.collapse', restore);
    adminNav.addEventListener('hide.bs.collapse', save);
    on(window, 'pagehide', save);
    on(window, 'pageshow', () => { applySidebar(); restoreGroups(); restore(); });
    on(desktop, 'change', () => { applySidebar(); restoreGroups(); restore(); });
  }
  const header = document.querySelector('[data-site-header]');
  if (header) {
    let queued = false;
    const update = () => {
      header.classList.toggle('is-scrolled', window.scrollY > 40);
      queued = false;
    };
    on(window, 'scroll', () => {
      if (!queued) { queued = true; requestAnimationFrame(update); }
    }, { passive: true });
    update();
  }
  document.querySelectorAll('#public-nav, #admin-nav').forEach(menu => {
    const toggle = document.querySelector('[aria-controls="' + menu.id + '"]');
    const opening = () => menu.id === 'public-nav' && menu.classList.contains('collapsing') && toggle?.getAttribute('aria-expanded') === 'true';
    const isOpen = () => toggle?.getClientRects().length && (menu.classList.contains('show') || opening());
    const closeMenu = () => {
      // Bootstrap ignores hide() during its opening transition. Honour an immediate Escape too.
      const hide = () => bootstrap.Collapse.getOrCreateInstance(menu, { toggle: false }).hide();
      if (opening()) menu.addEventListener('shown.bs.collapse', hide, { once: true });
      else hide();
    };
    on(document, 'keydown', event => {
      if (!event.defaultPrevented && event.key === 'Escape' && isOpen() && window.bootstrap) {
        event.preventDefault();
        closeMenu();
        toggle.focus({ preventScroll: true });
      }
    });
    // Keep a mobile menu from covering the next keyboard destination.
    on(document, 'focusin', event => {
      if (isOpen() && !menu.contains(event.target) && !toggle.contains(event.target) && window.bootstrap) {
        closeMenu();
      }
    });
  });
  // Django owns validation. This only links its rendered errors to the visible controls.
  document.querySelectorAll('.errorlist:not(.nonfield)').forEach(errors => {
    const wrapper = errors.parentElement;
    const field = wrapper.querySelector('input:not([type=hidden]),select,textarea');
    if (!field || !field.id || !errors.textContent.trim()) return;
    if (!errors.id) errors.id = field.id + '_errors';
    field.setAttribute('aria-invalid', 'true');
    const described = new Set((field.getAttribute('aria-describedby') || '').split(' ').filter(Boolean));
    described.add(errors.id);
    field.setAttribute('aria-describedby', [...described].join(' '));
  });
})();

});
