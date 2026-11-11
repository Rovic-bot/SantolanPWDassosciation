/* Accessible, server-validated announcement composer; ordinary form fallback remains. */
'use strict';
WorkspacePage.run(({on, fetch, cleanup}) => {
  const dialog = document.querySelector('[data-announcement-composer]');
  if (!dialog || !dialog.showModal) return;
  document.body.append(dialog);
  const host = dialog.querySelector('[data-composer-host]');
  const page = document.querySelector('[data-composer-page]');
  let trigger, pending, saving = false, previewURL;
  const clearPreview = () => { if (previewURL) URL.revokeObjectURL(previewURL); previewURL = null; };
  const focusForm = () => {
    dialog.setAttribute('aria-labelledby', 'announcement-composer-title');
    (host.querySelector('[data-composer-errors]:not([hidden])') || host.querySelector('[name=title]'))?.focus();
  };
  const show = () => { if (!dialog.open) dialog.showModal(); };
  const close = () => {
    if (saving) return;
    pending?.abort();
    if (page) location.assign(host.querySelector('[data-composer-close]').href);
    else dialog.close();
  };
  on(dialog, 'cancel', event => { event.preventDefault(); close(); });
  on(dialog, 'keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('a[href],button:not(:disabled),input:not([type=hidden]):not(:disabled),textarea:not(:disabled),select:not(:disabled),[tabindex="0"]')]
      .filter(element => element.checkVisibility({checkVisibilityCSS: true}));
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  on(dialog, 'close', () => { clearPreview(); host.replaceChildren(); trigger?.focus(); });
  on(dialog, 'click', event => {
    if (event.target.closest('[data-composer-close]')) { event.preventDefault(); close(); }
    if (event.target === dialog) {
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close();
    }
  });
  on(document, 'click', async event => {
    const link = event.target.closest('[data-announcement-create]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    trigger = link;
    pending?.abort();
    const request = new AbortController();
    pending = request;
    dialog.removeAttribute('aria-labelledby');
    host.innerHTML = '<div class="announcement-composer"><p role="status">Loading announcement editor…</p><button class="btn btn-outline-secondary" type="button" data-composer-close>Cancel</button></div>';
    show();
    try {
      const url = new URL(link.href);
      url.searchParams.set('popup', '1');
      const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', signal: request.signal });
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = doc.querySelector('[data-composer-content]');
      if (!response.ok || !content) throw new Error('unavailable');
      if (!dialog.open || pending !== request) return;
      host.replaceChildren(content);
      focusForm();
    } catch (error) {
      if (error.name !== 'AbortError') location.assign(link.href);
    }
  });
  on(dialog, 'change', event => {
    if (!event.target.matches('input[type=file][name=image]')) return;
    clearPreview();
    const preview = host.querySelector('[data-composer-preview]');
    const file = event.target.files[0];
    preview.hidden = !file || !['image/png', 'image/jpeg'].includes(file.type);
    if (preview.hidden) return;
    previewURL = URL.createObjectURL(file);
    preview.querySelector('img').src = previewURL;
    preview.querySelector('[data-composer-filename]').textContent = file.name;
  });
  on(dialog, 'click', event => {
    if (!event.target.closest('[data-composer-remove]')) return;
    clearPreview();
    host.querySelector('[name=image]').value = '';
    host.querySelector('[data-composer-preview]').hidden = true;
    host.querySelector('[name=image]').focus();
  });
  on(dialog, 'submit', async event => {
    const form = event.target.closest('[data-composer-form]');
    if (!form) return;
    event.preventDefault();
    if (saving) return;
    saving = true;
    const submit = form.querySelector('[type=submit]');
    const finish = window.ActionFeedback?.start(form, {button: submit, label: 'Saving draft…'});
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    const feedback = form.querySelector('[data-composer-feedback]');
    feedback.textContent = 'Saving your draft…';
    try {
      const url = new URL(form.action);
      url.searchParams.set('popup', '1');
      const response = await fetch(url, { method: 'POST', body: new FormData(form), credentials: 'same-origin' });
      if (response.ok && response.headers.get('content-type')?.includes('application/json')) {
        const result = await response.json();
        const destination = new URL(result.redirect, location.href);
        if (destination.origin !== location.origin) throw new Error('unavailable');
        location.assign(destination.href);
        return;
      }
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = doc.querySelector('[data-composer-content]');
      if (!content) throw new Error('unavailable');
      clearPreview();
      host.replaceChildren(content);
      focusForm();
    } catch (_) {
      feedback.textContent = 'The draft could not be saved. Your entered text is still here. Please try again.';
    } finally {
      finish?.();
      saving = false;
      submit.disabled = false;
      form.removeAttribute('aria-busy');
    }
  });
  cleanup(() => { pending?.abort(); clearPreview(); dialog.remove(); });
  if (page) {
    host.append(page.querySelector('[data-composer-content]'));
    page.hidden = true;
    show();
    focusForm();
  }
});
