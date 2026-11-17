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
  function apply(animate = false) {
    const theme = chosen || (preference.matches ? 'dark' : 'light');
    const update = () => {
      root.dataset.dashboardTheme = theme;
      document.dispatchEvent(new CustomEvent('santolan:adminthemechange', {detail: theme}));
      document.dispatchEvent(new Event('santolan:displaychange'));
    };
    if (animate && window.ThemeTransition) window.ThemeTransition.run(update);
    else update();
  }
  apply();
  on(document, 'santolan:setadmintheme', event => {
    if (!['dark', 'light'].includes(event.detail)) return;
    chosen = event.detail;
    try { localStorage.setItem(key, chosen); } catch (_) {}
    apply(true);
  });
  on(preference, 'change', () => { if (!chosen) apply(true); });
  addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    chosen = ['dark', 'light'].includes(event.newValue) ? event.newValue : undefined;
    apply(true);
  });

})();

});
