WorkspacePage.run(({on, addEventListener, setTimeout}) => {
/* Automatic GET filters only. Editing, approvals and other POST actions stay explicit. */
(() => {
  'use strict';
  if (!document.body.classList.contains('admin-workspace')) return;
  const forms = [...document.querySelectorAll('form[data-auto-filter], .native-admin-workspace #changelist-search')]
    .filter(form => form.method.toLowerCase() === 'get' && new URL(form.action).origin === location.origin);
  const focusKey = 'santolan:filter-focus';
  let timer;
  let composing = false;
  const textTypes = new Set(['text', 'search', 'number', 'email', 'tel', 'url']);

  function feedback(form, message) {
    form.querySelector('[data-auto-filter-feedback]').textContent = message;
  }

  function rangeReady(form) {
    if (!form.hasAttribute('data-auto-filter-custom-range')) return true;
    const custom = form.elements.namedItem('period')?.value === 'custom';
    form.querySelectorAll('[data-custom-date]').forEach(group => {
      group.hidden = !custom;
      group.querySelectorAll('input').forEach(input => { input.disabled = !custom; });
    });
    form.classList.toggle('has-custom-dates', custom);
    const ready = !custom || (form.elements.namedItem('start').value && form.elements.namedItem('end').value);
    if (!ready) feedback(form, 'Choose both a start and end date to apply this range.');
    return Boolean(ready);
  }

  function rememberFocus(form, control) {
    // Store only focus/scroll coordinates, never search text or applicant values.
    try {
      const state = {path: new URL(form.action).pathname, form: forms.indexOf(form),
        field: control?.name || '', start: control?.selectionStart, end: control?.selectionEnd,
        x: scrollX, y: scrollY, time: Date.now()};
      sessionStorage.setItem(focusKey, JSON.stringify(state));
    } catch (_) { /* Filters still work when browser storage is unavailable. */ }
  }

  function submit(form, control) {
    clearTimeout(timer);
    if (!rangeReady(form) || !form.checkValidity()) return;
    const submitter = textTypes.has(control.type) ? null : form.querySelector('[data-auto-filter-select-submit]');
    form.requestSubmit(submitter || undefined);
  }

  for (const form of forms) {
    const notice = document.createElement('span');
    notice.className = 'visually-hidden';
    notice.dataset.autoFilterFeedback = '';
    notice.setAttribute('role', 'status');
    form.append(notice);
    form.dataset.autoFilterReady = 'true';
    // Keep native submission available without JavaScript; remove only filter buttons.
    form.querySelectorAll('button:not([type]), button[type=submit], input[type=submit]').forEach(button => {
      button.hidden = true;
      const wrapper = button.parentElement;
      if (wrapper !== form && wrapper.children.length === 1 && !wrapper.textContent.replace(button.textContent, '').trim()) {
        wrapper.hidden = true;
      }
    });
    rangeReady(form);
    form.addEventListener('input', event => {
      const control = event.target;
      if (!control.name || !textTypes.has(control.type) || control.disabled || event.isComposing || composing) return;
      clearTimeout(timer);
      timer = setTimeout(() => submit(form, control), 400);
    });
    form.addEventListener('change', event => {
      const control = event.target;
      if (!control.name || control.disabled || textTypes.has(control.type) || control.type === 'hidden') return;
      if (control.matches('select, input[type=checkbox], input[type=radio], input[type=date], input[type=month], input[type=datetime-local]')) {
        submit(form, control);
      }
    });
    form.addEventListener('compositionstart', () => { composing = true; clearTimeout(timer); });
    form.addEventListener('compositionend', event => {
      composing = false;
      if (textTypes.has(event.target.type)) timer = setTimeout(() => submit(form, event.target), 400);
    });
    form.addEventListener('submit', event => {
      clearTimeout(timer);
      if (!rangeReady(form)) { event.preventDefault(); return; }
      // A changed filter always starts at the first page; retained run/context fields stay intact.
      form.querySelectorAll('input[type=hidden][name=page], input[type=hidden][name=p]').forEach(input => { input.disabled = true; });
      rememberFocus(form, document.activeElement?.form === form ? document.activeElement : null);
      feedback(form, 'Updating results…');
    });
  }

  // Do not let a pending search interrupt another action on the page.
  on(document, 'submit', event => { if (!forms.includes(event.target)) clearTimeout(timer); });
  on(document, 'input', event => { if (!forms.includes(event.target.form)) clearTimeout(timer); });
  on(document, 'click', event => {
    if (event.target.closest('a[href]') || (event.target.closest('button') && !forms.includes(event.target.closest('form')))) clearTimeout(timer);
  });
  addEventListener('pagehide', () => clearTimeout(timer));
  addEventListener('pageshow', () => {
    try {
      const state = JSON.parse(sessionStorage.getItem(focusKey) || 'null');
      sessionStorage.removeItem(focusKey);
      if (!state || state.path !== location.pathname || Date.now() - state.time > 30000) return;
      const form = forms[state.form];
      const control = form?.elements.namedItem(state.field);
      if (!control?.focus || control.disabled) return;
      control.focus({preventScroll: true});
      if (typeof state.start === 'number' && control.setSelectionRange) {
        control.setSelectionRange(state.start, state.end);
      }
      scrollTo({left: state.x, top: state.y, behavior: 'instant'});
      feedback(form, 'Filters applied.');
    } catch (_) { /* Native page navigation remains the fallback. */ }
  });
})();

});
