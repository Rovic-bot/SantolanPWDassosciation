/* One shared theme fade; initial theme restoration still happens before paint. */
WorkspacePage.run(page => {
  'use strict';
  const {on, cleanup, setTimeout} = page;
  const root = document.documentElement;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let active, pendingUpdate, timer;
  const enabled = () => root.dataset.motion !== 'reduce' && !reducedMotion.matches &&
    document.visibilityState === 'visible';
  const flush = () => {
    const update = pendingUpdate;
    pendingUpdate = undefined;
    update?.();
  };
  const finish = () => {
    const previous = active;
    active = undefined;
    previous?.skipTransition();
    flush();
    window.clearTimeout(timer);
    delete root.dataset.themeTransition;
  };
  const run = update => {
    finish();
    if (!enabled()) { update(); return; }
    if (!document.startViewTransition) {
      root.dataset.themeTransition = 'colors';
      // Commit the temporary transitions before changing the palette.
      void root.offsetWidth;
      update();
      timer = setTimeout(finish, 400);
      return;
    }
    root.dataset.themeTransition = 'fade';
    pendingUpdate = update;
    try {
      const transition = document.startViewTransition(() => {
        if (pendingUpdate === update) flush();
      });
      active = transition;
      // Rapid toggles, navigation or a hidden tab can skip snapshot capture.
      transition.ready.catch(() => {});
      const settle = () => { if (active === transition) finish(); };
      transition.finished.then(settle, settle);
    } catch (_) {
      finish();
    }
  };
  const respectMotion = () => { if (!enabled()) finish(); };
  on(reducedMotion, 'change', respectMotion);
  on(document, 'santolan:displaychange', respectMotion);
  on(document, 'visibilitychange', respectMotion);
  cleanup(finish);
  window.ThemeTransition = {run};
});
