/* Presentation only: this notice does not record consent or change submission rules. */
(() => {
  'use strict';
  const form = document.querySelector('.public-portal [data-registration-privacy-form]');
  const dialog = document.querySelector('[data-registration-privacy-dialog]');
  const notice = document.querySelector('[data-registration-privacy-notice]');
  const controls = document.querySelector('[data-registration-privacy-controls]');
  if (!form || !dialog || !notice || !controls || typeof dialog.showModal !== 'function') return;

  const content = dialog.querySelector('[data-registration-privacy-content]');
  const title = notice.querySelector('h2');
  const opener = controls.querySelector('[data-registration-privacy-open]');
  const closeButton = dialog.querySelector('[data-registration-privacy-close]');
  let shown = false;
  let returnFocus = opener;

  content.append(notice);
  controls.hidden = false;

  const open = target => {
    if (dialog.open) return;
    shown = true;
    returnFocus = target;
    dialog.showModal();
    document.body.classList.add('registration-privacy-open');
    content.scrollTop = 0;
    title.focus({ preventScroll: true });
  };
  const fieldFor = target => {
    const field = target.closest('input,select,textarea') || target.closest('label')?.control;
    return field && form.contains(field) && !['hidden', 'submit', 'button', 'reset'].includes(field.type) &&
      !field.disabled && !field.readOnly ? field : null;
  };

  // Show once per page, before a pointer opens a native select or date control.
  form.addEventListener('pointerdown', event => {
    if (shown || event.button !== 0) return;
    const field = fieldFor(event.target);
    if (!field) return;
    event.preventDefault();
    open(field);
  });
  // Keyboard and assistive-technology users receive the same notice.
  form.addEventListener('focusin', event => {
    if (shown) return;
    const field = fieldFor(event.target);
    if (field) open(field);
  });
  opener.addEventListener('click', () => open(opener));
  closeButton.addEventListener('click', () => dialog.close());
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const focusable = [...dialog.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
      .filter(element => element.getClientRects().length);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const current = document.activeElement;
    if (!focusable.includes(current) || (event.shiftKey && current === first) || (!event.shiftKey && current === last)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  });
  dialog.addEventListener('close', () => {
    document.body.classList.remove('registration-privacy-open');
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  });
})();
