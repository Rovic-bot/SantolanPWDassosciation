/* Enhance the server-confirmed receipt only; no submission or email is repeated. */
WorkspacePage.run(page => {
  'use strict';
  const {on, cleanup} = page;
  const content = document.querySelector('[data-member-update-confirmation]');
  const dialog = document.querySelector('[data-member-update-confirmation-dialog]');
  const finish = document.getElementById('member-update-finish');
  if (!content || !finish || typeof dialog?.showModal !== 'function') return;
  dialog.querySelector('[data-member-update-confirmation-body]').append(content);
  dialog.showModal();
  document.documentElement.classList.add('member-update-confirmation-open');
  content.querySelector('h1').focus({preventScroll: true});
  on(dialog, 'cancel', event => {
    event.preventDefault();
    finish.requestSubmit();
  });
  on(dialog, 'keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('button:not(:disabled), a[href]')];
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && (document.activeElement === first || document.activeElement.tabIndex < 0)) {
      event.preventDefault(); last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first?.focus();
    }
  });
  cleanup(() => document.documentElement.classList.remove('member-update-confirmation-open'));
});
