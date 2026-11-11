WorkspacePage.run(({on, addEventListener, IntersectionObserver}) => {
/* Enhance the shared editor; the existing protected multipart form saves changes. */
(() => {
  'use strict';
  const root = document.querySelector('[data-event-builder]');
  if (!root || !window.SantolanScheduleCalendar) return;
  const form = root.querySelector('[data-event-form]');
  const imageInput = form.elements.namedItem('image');
  const preview = root.querySelector('[data-image-preview]');
  const imageFeedback = root.querySelector('[data-image-feedback]');
  const validation = root.querySelector('[data-event-validation]');
  const calendar = root.querySelector('[data-event-calendar]');
  const editing = root.dataset.editing === 'true';
  let range, imageURL, submitting = false;
  const value = name => form.elements.namedItem(name).value.trim();
  const fingerprint = () => JSON.stringify([...new FormData(form)].filter(([name]) => name !== 'csrfmiddlewaretoken')
    .map(([name, data]) => [name, data instanceof File ? (data.name ? `${data.name}:${data.size}:${data.lastModified}` : '') : data]));
  const formatDateTime = raw => raw ? new Intl.DateTimeFormat('en-PH', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC'
  }).format(new Date(`${raw}Z`)) : 'Choose a date and time';
  function update() {
    root.querySelector('[data-event-title]').textContent = value('title') || 'Untitled event';
    root.querySelector('[data-event-location]').textContent = value('location') || 'Location not set';
    root.querySelector('[data-event-start]').textContent = range?.complete() ? formatDateTime(value('starts_at')) : 'Choose a date and time';
    root.querySelector('[data-event-end]').textContent = range?.complete() ? formatDateTime(value('ends_at')) : 'Choose a date and time';
    if (range && validation.dataset.client === 'true') check(false);
  }
  function check(focus = true) {
    const errors = [];
    for (const input of form.querySelectorAll('input[name],textarea[name]')) {
      if (input.closest('[data-native-dates]')) continue;
      if (!input.checkValidity()) {
        const label = root.querySelector(`label[for="${CSS.escape(input.id)}"]`)?.textContent.replace(/\s*\*$/, '').trim() || input.name;
        errors.push({text: `${label}: ${input.validationMessage}`, target: input});
        input.setAttribute('aria-invalid', 'true');
      }
    }
    if (range.error()) errors.push({text: `Event schedule: ${range.error()}`, target: calendar, calendar: true});
    validation.dataset.client = 'true';
    validation.hidden = !errors.length;
    if (errors.length) {
      const list = document.createElement('ul');
      for (const error of errors) {
        const item = document.createElement('li'), link = document.createElement('a');
        link.href = `#${error.target.id || 'event-schedule'}`; link.textContent = error.text;
        link.addEventListener('click', event => { event.preventDefault(); error.calendar ? range.focus() : error.target.focus(); });
        item.append(link); list.append(item);
      }
      validation.querySelector('[data-validation-content]').replaceChildren(list);
      if (focus) validation.focus();
    }
    return !errors.length;
  }
  function updateImage() {
    if (imageURL) { URL.revokeObjectURL(imageURL); imageURL = null; }
    preview.hidden = true;
    imageInput.setCustomValidity('');
    imageInput.removeAttribute('aria-invalid');
    imageFeedback.textContent = '';
    imageFeedback.dataset.error = 'false';
    const file = imageInput.files[0];
    if (!file) return;
    const limit = Number(root.dataset.imageLimit) * 1048576;
    const error = !['image/png', 'image/jpeg'].includes(file.type) ? 'Choose a PNG or JPEG image.' :
      file.size > limit ? `Choose an image no larger than ${root.dataset.imageLimit} MB.` : '';
    if (error) {
      imageInput.setCustomValidity(error); imageInput.setAttribute('aria-invalid', 'true');
      imageFeedback.textContent = error; imageFeedback.dataset.error = 'true'; return;
    }
    imageURL = URL.createObjectURL(file);
    root.querySelector('[data-image-thumbnail]').src = imageURL;
    root.querySelector('[data-image-name]').textContent = file.name;
    root.querySelector('[data-image-size]').textContent = `${Math.max(1, Math.round(file.size / 1024))} KB`;
    preview.hidden = false;
    imageFeedback.textContent = editing ? 'Replacement selected. Save changes to upload it.' : 'Image selected. Save the draft to upload it.';
  }
  range = window.SantolanScheduleCalendar(calendar, form, update).get('event');
  form.noValidate = true;
  imageInput.setAttribute('aria-describedby', 'event-image-help');
  update();
  const initial = fingerprint();
  form.addEventListener('input', event => {
    root.querySelector('[data-event-status]').textContent = 'Unsaved changes';
    if (event.target.checkValidity?.()) event.target.removeAttribute('aria-invalid');
    update();
  });
  form.addEventListener('change', update);
  imageInput.addEventListener('change', () => { updateImage(); update(); });
  root.querySelector('[data-remove-image]').addEventListener('click', () => {
    imageInput.value = ''; updateImage(); update(); imageInput.focus(); imageFeedback.textContent = 'Selected image removed.';
  });
  form.addEventListener('submit', event => {
    if (submitting || !check()) { event.preventDefault(); return; }
    submitting = true;
    root.querySelector('[data-save-event]').disabled = true;
    root.querySelector('[data-event-status]').textContent = editing ? 'Saving changes' : 'Saving draft';
    root.querySelector('[data-event-save-feedback]').textContent = 'Saving event…';
  });
  const setStep = id => root.querySelectorAll('.builder-steps > a').forEach(link => {
    if (link.hash === `#${id}`) link.setAttribute('aria-current', 'step'); else link.removeAttribute('aria-current');
  });
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) setStep(entry.target.id);
  }, {rootMargin: '-100px 0px -45% 0px'});
  root.querySelectorAll('.builder-section').forEach(section => observer.observe(section));
  root.querySelectorAll('.builder-steps > a').forEach(link => link.addEventListener('click', () => setStep(link.hash.slice(1))));
  // Date errors remain reachable after progressive enhancement hides native controls.
  validation.querySelectorAll('a[href="#id_starts_at"],a[href="#id_ends_at"]').forEach(link => {
    link.href = '#event-schedule'; link.addEventListener('click', event => { event.preventDefault(); range.focus(); });
  });
  if (!validation.hidden) validation.focus();
  addEventListener('beforeunload', event => {
    if (!submitting && (fingerprint() !== initial || range.pending())) { event.preventDefault(); event.returnValue = ''; }
  });
  addEventListener('pageshow', event => {
    if (event.persisted) { submitting = false; root.querySelector('[data-save-event]').disabled = false;
      root.querySelector('[data-event-status]').textContent = 'Unsaved changes';
      root.querySelector('[data-event-save-feedback]').textContent = editing ? 'Save changes to update this event.' : 'Save a private draft, then review it before publishing.'; }
  });
})();

});
