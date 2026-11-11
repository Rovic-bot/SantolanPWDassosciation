WorkspacePage.run(({on}) => {
/* Presentation only. Existing POST forms retain all server-side publication guards. */
(() => {
  'use strict';
  function initialize(root) {
    if (!root) return;
    root.querySelectorAll('details').forEach((details) => {
      const summary = details.querySelector(':scope > summary');
      if (!summary) return;
      const sync = () => summary.setAttribute('aria-expanded', String(details.open));
      details.addEventListener('toggle', sync);
      sync();
    });
    const errors = root.querySelector('.alert-danger[role="alert"], #error-summary');
    if (errors) {
      errors.tabIndex = -1;
      errors.focus();
    } else {
      const reason = root.querySelector('[data-program-archive-review] [name="notes"]');
      if (reason) reason.focus();
    }
  }
  initialize(document.querySelector('[data-program-profile], [data-event-profile]'));
  on(document, 'program-details:loaded', event => initialize(event.detail.root));
})();

});
