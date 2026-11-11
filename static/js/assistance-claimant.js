'use strict';
WorkspacePage.run(({on, cleanup}) => {
  function sync(form) {
    const representative = form.elements.claimant_type.value === 'representative';
    const fields = form.querySelector('[data-representative-fields]');
    fields.hidden = !representative;
    fields.disabled = !representative;
    fields.querySelectorAll('[data-representative-input]').forEach(input => { input.required = representative; });
  }
  function initialize() { document.querySelectorAll('[data-claimant-form]').forEach(sync); }
  on(document, 'change', event => {
    if (event.target.name === 'claimant_type' && event.target.closest('[data-claimant-form]')) sync(event.target.form);
  });
  on(document, 'assistance-claimant:loaded', initialize);
  initialize();
});
