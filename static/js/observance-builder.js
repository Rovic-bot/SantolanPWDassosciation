'use strict';
WorkspacePage.run(({on, addEventListener, IntersectionObserver, cleanup}) => {
  const root = document.querySelector('[data-observance-builder]');
  if (!root) return;
  const form = root.querySelector('[data-observance-form]');
  const field = name => form.elements.namedItem(name);
  const start = field('start_date'), end = field('end_date'), image = field('image');
  const preview = root.querySelector('[data-image-preview]');
  const feedback = root.querySelector('[data-image-feedback]');
  const save = root.querySelector('[data-save-observance]');
  const state = root.querySelector('[data-observance-status]');
  const saveFeedback = root.querySelector('[data-save-feedback]');
  const savedGuidance = saveFeedback.textContent;
  const calendar = root.querySelector('[data-observance-calendar]');
  let range;
  const format = raw => new Intl.DateTimeFormat('en-PH', {
    month: 'long', day: 'numeric', timeZone: 'UTC'
  }).format(new Date(raw + 'T12:00:00Z'));
  const fingerprint = () => JSON.stringify([...new FormData(form)]
    .filter(([name]) => name !== 'csrfmiddlewaretoken')
    .map(([name, value]) => [name, value instanceof File ? (value.name ? [value.name, value.size, value.lastModified] : '') : value]));
  let imageURL, submitting = false;
  const releaseImage = () => {
    if (imageURL) URL.revokeObjectURL(imageURL);
    imageURL = null;
  };
  cleanup(releaseImage);
  function update() {
    root.querySelector('[data-observance-title]').textContent = field('title').value.trim() || 'Untitled observance';
    root.querySelector('[data-observance-audience]').textContent = field('target_audience').value.trim() || 'Audience not set';
    start.setCustomValidity('');
    end.setCustomValidity('');
    if (Boolean(start.value) !== Boolean(end.value)) {
      (start.value ? end : start).setCustomValidity('Choose both the start and end dates.');
    } else if (start.value && end.value) {
      if (start.value.slice(5, 7) !== end.value.slice(5, 7)) {
        end.setCustomValidity('Choose an end date in the same observance month.');
      } else if (end.value.slice(8) < start.value.slice(8)) {
        end.setCustomValidity('The end date must be on or after the start date.');
      }
    }
    root.querySelector('[data-observance-dates]').textContent = range?.error() ? 'Choose a valid start and end date' : start.value && end.value &&
      start.validity.valid && end.validity.valid ?
      (start.value.slice(5) === end.value.slice(5) ? format(start.value) : format(start.value) + ' – ' + format(end.value)) :
      root.dataset.currentSchedule;
  }
  function updateImage() {
    releaseImage();
    preview.hidden = true;
    image.setCustomValidity('');
    feedback.textContent = '';
    feedback.dataset.error = 'false';
    const file = image.files[0];
    if (!file) return;
    const error = !['image/png', 'image/jpeg'].includes(file.type) ? 'Choose a PNG or JPEG image.' :
      file.size > Number(root.dataset.imageLimit) * 1048576 ? 'Choose an image no larger than ' + root.dataset.imageLimit + ' MB.' : '';
    if (error) {
      image.setCustomValidity(error);
      feedback.textContent = error;
      feedback.dataset.error = 'true';
      return;
    }
    const removal = field('remove_image');
    if (removal) removal.checked = false;
    imageURL = URL.createObjectURL(file);
    root.querySelector('[data-image-thumbnail]').src = imageURL;
    root.querySelector('[data-image-name]').textContent = file.name;
    root.querySelector('[data-image-size]').textContent = Math.max(1, Math.round(file.size / 1024)) + ' KB';
    preview.hidden = false;
    feedback.textContent = 'Image selected. Save the observance to upload it.';
  }
  if (calendar && window.SantolanScheduleCalendar) {
    range = window.SantolanScheduleCalendar(calendar, form, () => {
      state.textContent = 'Unsaved changes';
      update();
    }).get('observance');
    form.noValidate = true;
    root.querySelectorAll('a[href="#id_start_date"], a[href="#id_end_date"]').forEach(link => {
      link.href = '#observance-dates';
      on(link, 'click', event => { event.preventDefault(); range.focus(); });
    });
  }
  image.setAttribute('aria-describedby', 'observance-image-help');
  update();
  const initial = fingerprint();
  on(form, 'input', () => { state.textContent = 'Unsaved changes'; update(); });
  on(form, 'change', update);
  on(image, 'change', updateImage);
  on(root.querySelector('[data-remove-image]'), 'click', () => {
    image.value = '';
    updateImage();
    image.focus();
    feedback.textContent = 'Selected image removed.';
  });
  on(form, 'submit', event => {
    update();
    if (range?.error()) {
      event.preventDefault();
      range.focus();
      calendar.querySelector('[data-range-feedback]').textContent = range.error();
      return;
    }
    if (submitting || !form.reportValidity()) { event.preventDefault(); return; }
    submitting = true;
    save.disabled = true;
    state.textContent = 'Saving changes';
    root.querySelector('[data-save-feedback]').textContent = 'Saving observance…';
  });
  const setStep = id => root.querySelectorAll('.builder-steps > a').forEach(link => {
    if (link.hash === '#' + id) link.setAttribute('aria-current', 'step');
    else link.removeAttribute('aria-current');
  });
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) setStep(entry.target.id); });
  }, {rootMargin: '-100px 0px -45% 0px'});
  root.querySelectorAll('.builder-section').forEach(section => observer.observe(section));
  root.querySelectorAll('.builder-steps > a').forEach(link =>
    on(link, 'click', () => setStep(link.hash.slice(1))));
  root.querySelector('.builder-validation')?.focus();
  addEventListener('beforeunload', event => {
    if (!submitting && (fingerprint() !== initial || range?.pending())) { event.preventDefault(); event.returnValue = ''; }
  });
  addEventListener('pageshow', event => {
    if (!event.persisted) return;
    submitting = false;
    save.disabled = false;
    state.textContent = 'Unsaved changes';
    saveFeedback.textContent = savedGuidance;
  });
});
