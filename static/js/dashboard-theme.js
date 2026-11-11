WorkspacePage.run(({on, addEventListener}) => {
/* Shared admin theme, set before paint. Retain the existing dashboard preference key. */
(() => {
  'use strict';
  const root = document.documentElement;
  const preference = matchMedia('(prefers-color-scheme: dark)');
  const key = 'santolan-dashboard-theme';
  let chosen;
  try {
    const saved = localStorage.getItem(key);
    if (['dark', 'light'].includes(saved)) chosen = saved;
  } catch (_) { /* The switch works even without storage. */ }
  function apply() {
    root.dataset.dashboardTheme = chosen || (preference.matches ? 'dark' : 'light');
    document.dispatchEvent(new CustomEvent('santolan:adminthemechange', {detail: root.dataset.dashboardTheme}));
    document.dispatchEvent(new Event('santolan:displaychange'));
  }
  apply();
  on(document, 'santolan:setadmintheme', event => {
    if (!['dark', 'light'].includes(event.detail)) return;
    chosen = event.detail;
    try { localStorage.setItem(key, chosen); } catch (_) {}
    apply();
  });
  on(preference, 'change', () => { if (!chosen) apply(); });
  addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    chosen = ['dark', 'light'].includes(event.newValue) ? event.newValue : undefined;
    apply();
  });

})();

});
