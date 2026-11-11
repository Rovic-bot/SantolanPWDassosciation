WorkspacePage.run(({on}) => {
/* Progressive enhancement for onsite intake. Personal data stays in the page. */
(() => {
  'use strict';
  function updateFile(input) {
    const field = input.closest('.onsite-field');
    const files = [...input.files];
    field.querySelector('[data-file-status]').textContent = files.length ? files.map(file =>
      `${file.name} · ${new Intl.NumberFormat().format(Math.ceil(file.size / 1024))} KB`).join(', ') :
      'No file selected';
    field.querySelector('[data-clear-upload]').hidden = !files.length;
  }
  document.querySelectorAll('.onsite-field input[type="file"]').forEach(input => {
    const field = input.closest('.onsite-field');
    input.addEventListener('change', () => updateFile(input));
    field.querySelector('[data-clear-upload]').addEventListener('click', () => {
      input.value = '';
      input.dispatchEvent(new Event('change', {bubbles: true}));
      input.focus();
    });
    updateFile(input);
  });
  const form = document.querySelector('[data-onsite-form]');
  const dialog = document.querySelector('[data-onsite-review-dialog]');
  if (!form || !dialog?.showModal) return;

  const sections = [...form.querySelectorAll('[data-onsite-section]')];
  const summary = form.querySelector('[data-onsite-validation]');
  const feedback = form.querySelector('[data-save-feedback]');
  const reviewButton = form.querySelector('[data-review-application]');
  const submitButton = form.querySelector('[data-save-registration]');
  const confirmButton = dialog.querySelector('[data-confirm-registration]');
  const confirmLabel = confirmButton.textContent;
  const status = document.querySelector('[data-record-status]');
  const updated = document.querySelector('[data-record-updated]');
  const controlsIn = root => [...root.querySelectorAll('input:not([type=hidden]), select, textarea')];
  const controls = controlsIn(form);
  const fileControls = controls.filter(input => input.type === 'file');
  let confirmed = false;
  let reviewOpener = reviewButton;

  form.noValidate = true;
  reviewButton.hidden = false;
  submitButton.hidden = true;
  const setStatus = (label, detail) => { status.textContent = label; updated.textContent = detail; };
  const fieldLabel = input => input.closest('[data-field-label]')?.dataset.fieldLabel || input.name;

  function validateFiles() {
    let total = 0;
    fileControls.forEach(input => {
      input.setCustomValidity('');
      const allowed = input.accept.toLowerCase().split(',').map(item => item.trim()).filter(Boolean);
      [...input.files].forEach(file => {
        total += file.size;
        if (Number(form.dataset.fileLimit) && file.size > Number(form.dataset.fileLimit)) {
          input.setCustomValidity('This file exceeds the per-file size limit. Choose a smaller file.');
        } else if (allowed.length && !allowed.some(type => type.startsWith('.') ? file.name.toLowerCase().endsWith(type) :
          type.endsWith('/*') ? file.type.toLowerCase().startsWith(type.slice(0, -1)) : file.type.toLowerCase() === type)) {
          input.setCustomValidity('Choose one of the file types listed for this document.');
        }
      });
    });
    const selected = fileControls.find(input => input.files.length);
    if (selected && Number(form.dataset.totalLimit) && total > Number(form.dataset.totalLimit)) {
      selected.setCustomValidity('The selected files exceed the combined size limit. Remove or reduce a file.');
    }
    const civilFile = form.elements.namedItem('civil_document');
    const civilType = form.elements.namedItem('civil_alternative');
    if (civilFile && civilType) civilType.setCustomValidity(Boolean(civilFile.files.length) === Boolean(civilType.value) ? '' :
      civilFile.files.length ? 'Select Birth Certificate or Marriage Certificate for the uploaded document.' :
        'Attach the matching civil document, or select No civil document uploaded.');
  }

  function markChanged() {
    validateFiles();
    if (!summary.hidden) {
      summary.querySelectorAll('[data-error-for]').forEach(item => {
        if (document.getElementById(item.dataset.errorFor)?.validity.valid) item.remove();
      });
      summary.hidden = !summary.querySelector('li');
    }
    setStatus('Unsaved changes', 'Not yet submitted');
    feedback.textContent = 'Review the application when you are ready to submit.';
  }
  form.addEventListener('input', event => {
    if (event.target.validity?.valid) event.target.removeAttribute('aria-invalid');
    markChanged();
  });
  form.addEventListener('change', markChanged);

  function scrollToTarget(target, focus = false) {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.motion === 'reduce';
    target.scrollIntoView({behavior: reduced ? 'instant' : 'smooth', block: 'start'});
    if (focus) target.focus({preventScroll: true});
  }
  function validate() {
    validateFiles();
    const invalid = controls.filter(input => input.willValidate && !input.validity.valid);
    summary.querySelector('ul').replaceChildren();
    controls.forEach(input => { if (input.validity?.valid) input.removeAttribute('aria-invalid'); });
    summary.hidden = !invalid.length;
    if (!invalid.length) return true;
    invalid.forEach(input => {
      input.setAttribute('aria-invalid', 'true');
      const item = document.createElement('li');
      item.dataset.errorFor = input.id;
      const anchor = document.createElement('a');
      anchor.href = `#${input.id}`;
      anchor.textContent = `${fieldLabel(input)}: ${input.validationMessage}`;
      anchor.addEventListener('click', event => { event.preventDefault(); input.focus(); input.scrollIntoView({block: 'center'}); });
      item.append(anchor);
      summary.querySelector('ul').append(item);
    });
    setStatus('Check required fields', 'Not yet submitted');
    feedback.textContent = `${invalid.length} ${invalid.length === 1 ? 'field needs' : 'fields need'} your attention.`;
    scrollToTarget(summary, true);
    return false;
  }

  function reviewValue(field) {
    const inputs = controlsIn(field).filter(input => input.name && !input.disabled);
    if (!inputs.length) return 'Not provided';
    if (inputs[0].type === 'checkbox' && inputs.length > 1) {
      return inputs.filter(input => input.checked).map(input => input.closest('label')?.textContent.trim() || input.value).join(', ') || 'Not selected';
    }
    return inputs.map(input => {
      if (input.type === 'checkbox') return input.checked ? 'Confirmed' : 'Not confirmed';
      if (input.type === 'file') return [...input.files].map(file => file.name).join(', ') ||
        'No file selected';
      if (input.options) return input.value ? [...input.selectedOptions].map(option => option.textContent.trim()).join(', ') : 'Not provided';
      return input.value.trim() || 'Not provided';
    }).join(' · ');
  }
  function buildReview() {
    const content = dialog.querySelector('[data-review-content]');
    content.replaceChildren();
    sections.forEach(section => {
      const group = document.createElement('section');
      const heading = document.createElement('h3');
      heading.textContent = section.querySelector('h2').textContent;
      const list = document.createElement('dl');
      section.querySelectorAll('[data-field-label]').forEach(field => {
        if (field.hidden) return;
        const row = document.createElement('div');
        const label = document.createElement('dt');
        label.textContent = field.dataset.fieldLabel;
        const value = document.createElement('dd');
        value.textContent = reviewValue(field);
        row.append(label, value);
        list.append(row);
      });
      group.append(heading, list);
      content.append(group);
    });
  }
  form.addEventListener('submit', event => {
    if (confirmed) return;
    event.preventDefault();
    if (!validate()) return;
    reviewOpener = document.activeElement;
    buildReview();
    setStatus('Ready for review', 'Not yet submitted');
    dialog.showModal();
    dialog.querySelector('.onsite-review-body').scrollTop = 0;
  });
  dialog.querySelectorAll('[data-close-review]').forEach(button => button.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const focusable = [...dialog.querySelectorAll('button:not(:disabled), [href], [tabindex="0"]')]
      .filter(node => node.getClientRects().length);
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  dialog.addEventListener('close', () => { reviewOpener?.focus({preventScroll: true}); });
  confirmButton.addEventListener('click', () => {
    if (!validate()) { dialog.close(); scrollToTarget(summary, true); return; }
    const number = form.elements.namedItem('pwd_number')?.value;
    const opened = form.elements.namedItem('prpwd_lookup_number');
    if (opened && window.SantolanPrpwd?.open(form.dataset.prpwdUrl, number,
        form.querySelector('[data-save-feedback]'))) opened.value = number;
    confirmed = true;
    confirmButton.disabled = true;
    confirmButton.textContent = 'Saving registration…';
    form.requestSubmit(submitButton);
  });

  const lookup = document.querySelector('[data-onsite-lookup]');
  lookup?.addEventListener('submit', () => {
    lookup.setAttribute('aria-busy', 'true');
    lookup.querySelector('[data-lookup-button]').textContent = 'Loading application…';
    lookup.querySelector('[data-lookup-status]').textContent = 'Opening the existing application.';
  });
  on(window, 'pageshow', event => {
    confirmed = false;
    confirmButton.disabled = false;
    confirmButton.textContent = confirmLabel;
    lookup?.removeAttribute('aria-busy');
    if (lookup) lookup.querySelector('[data-lookup-button]').textContent = 'Load online application';
    if (event.persisted) { if (dialog.open) dialog.close(); markChanged(); }
  });
  const serverErrors = form.querySelector('#registration-errors');
  if (serverErrors) scrollToTarget(serverErrors, true);
})();

});
