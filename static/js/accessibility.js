WorkspacePage.run(({on}) => {
/* Display preferences contain no personal or application data. */
(() => {
  'use strict';
  const root = document.documentElement;
  const widget = document.querySelector('[data-display-widget]');
  if (!widget) return;
  const isPublic = document.body.classList.contains('public-portal');
  const isAdmin = document.body.classList.contains('admin-workspace');
  const defaults = { text: 'default', contrast: false, motion: false, dark: false, language: 'en' };
  let preferences = { ...defaults };
  try {
    const saved = JSON.parse(localStorage.getItem('santolan-display') || '{}');
    preferences = {
      text: ['default', 'large', 'largest'].includes(saved.text) ? saved.text : 'default',
      contrast: saved.contrast === true,
      motion: saved.motion === true,
      dark: saved.dark === true,
      language: saved.language === 'tl' ? 'tl' : 'en'
    };
  } catch (_) { /* The controls still work when browser storage is unavailable. */ }
  if (isAdmin) {
    try { preferences.language = localStorage.getItem('santolan-admin-language') === 'tl' ? 'tl' : 'en'; }
    catch (_) { preferences.language = 'en'; }
  }
  const trigger = widget.querySelector('.display-trigger');
  const panel = widget.querySelector('.display-panel');
  const status = widget.querySelector('[data-display-status]');
  const language = widget.querySelector('[data-public-language]');
  if (!isPublic && !document.body.classList.contains('admin-workspace')) {
    widget.querySelector('[data-preference="dark"]').closest('label').style.display = 'none';
  }
  if (!isPublic) preferences.dark = root.dataset.dashboardTheme === 'dark';
  if (language && (isAdmin || (isPublic && !document.querySelector('[data-portal-page]')))) language.hidden = false;
  const otherOpeners = [...document.querySelectorAll('[data-open-display]')];
  const expanded = value => {
    for (const opener of [trigger, ...otherOpeners]) opener.setAttribute('aria-expanded', String(value));
  };
  let returnFocus = trigger;
  const apply = (announce = false, themeChanged = false) => {
    root.dataset.text = preferences.text;
    root.dataset.contrast = String(preferences.contrast);
    root.dataset.motion = preferences.motion ? 'reduce' : 'system';
    if (isPublic) {
      root.dataset.publicTheme = preferences.dark ? 'dark' : 'light';
      root.dataset.language = preferences.language;
      language?.setAttribute('aria-pressed', String(preferences.language === 'tl'));
    } else if (themeChanged) {
      document.dispatchEvent(new CustomEvent('santolan:setadmintheme', {detail: preferences.dark ? 'dark' : 'light'}));
    }
    if (isAdmin) {
      root.dataset.language = preferences.language;
      language?.setAttribute('aria-pressed', String(preferences.language === 'tl'));
      try { localStorage.setItem('santolan-admin-language', preferences.language); } catch (_) {}
    }
    widget.querySelectorAll('[data-preference]').forEach(control => {
      const value = preferences[control.dataset.preference];
      if (control.type === 'checkbox') control.checked = value;
      else control.value = value;
    });
    try {
      const saved = JSON.parse(localStorage.getItem('santolan-display') || '{}');
      localStorage.setItem('santolan-display', JSON.stringify({...preferences, ...(!isPublic ? {dark: saved.dark === true, language: saved.language === 'tl' ? 'tl' : 'en'} : {})}));
    } catch (_) {}
    document.dispatchEvent(new CustomEvent('santolan:displaychange'));
    if (announce) status.textContent = 'Display preferences updated.';
  };
  const close = (restore = true) => {
    if (panel.hidden) return;
    panel.hidden = true;
    expanded(false);
    if (restore) {
      const opener = returnFocus.getClientRects().length ? returnFocus :
        (returnFocus.closest('#public-nav') && document.querySelector('[aria-controls="public-nav"]')) || trigger;
      opener.focus();
    }
  };
  const open = opener => {
    returnFocus = opener;
    panel.hidden = false;
    expanded(true);
    panel.querySelector('select').focus();
  };
  trigger.addEventListener('click', () => panel.hidden ? open(trigger) : close());
  widget.querySelector('.display-close').addEventListener('click', () => close());
  widget.querySelector('.display-reset').addEventListener('click', () => {
    preferences = { ...defaults };
    apply(true, true);
    status.textContent = 'Display preferences reset.';
  });
  widget.querySelectorAll('[data-preference]').forEach(control => control.addEventListener('change', () => {
    preferences[control.dataset.preference] = control.type === 'checkbox' ? control.checked : control.value;
    apply(true, control.dataset.preference === 'dark');
  }));
  otherOpeners.forEach(button => {
    button.setAttribute('aria-controls', panel.id);
    button.setAttribute('aria-expanded', 'false');
    button.hidden = false;
    button.addEventListener('click', () => open(button));
  });
  if (language) on(language, 'click', () => {
    preferences.language = preferences.language === 'tl' ? 'en' : 'tl';
    apply(true);
  });
  on(document, 'santolan:adminthemechange', event => {
    if (isPublic) return;
    preferences.dark = event.detail === 'dark';
    widget.querySelector('[data-preference="dark"]').checked = preferences.dark;
  });
  on(document, 'keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) {
      event.preventDefault();
      close();
    }
  });
  on(document, 'pointerdown', event => {
    if (!panel.hidden && !widget.contains(event.target) && !event.target.closest('[data-open-display]')) close(false);
  });
  // A nonmodal disclosure: tabbing back to page content closes it without trapping focus.
  on(document, 'focusin', event => {
    if (!panel.hidden && !widget.contains(event.target)) close(false);
  });
  apply();
  widget.hidden = false;
})();

});
