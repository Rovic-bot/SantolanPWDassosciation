'use strict';
WorkspacePage.run(({on, fetch, cleanup}) => {
  const root = document.querySelector('[data-portal-editor]');
  if (!root) return;
  const config = JSON.parse(document.getElementById('portal-editor-config').textContent);
  const frame = root.querySelector('[data-editor-frame]');
  const status = root.querySelector('[data-editor-status]');
  const error = root.querySelector('[data-editor-error]');
  const save = root.querySelector('[data-editor-save]');
  const discard = root.querySelector('[data-editor-discard]');
  const loading = root.querySelector('[data-editor-loading]');
  const pictureDialog = root.querySelector('[data-editor-picture-dialog]');
  const fileInput = root.querySelector('[data-picture-file]');
  const altInput = root.querySelector('[data-picture-alt]');
  let page = config.selected, version = 0, mode = config.canEdit ? 'edit' : 'preview';
  let changes = {}, files = {}, resets = new Set(), blobs = {}, saving = false, ready = false, uncertain = false, chosenPicture, chosenHasImage;
  let loadVersion = 0, hasDraft = false;
  const dirty = () => Object.keys(changes).length || Object.keys(files).length || resets.size;
  const send = data => frame.contentWindow?.postMessage({portalEditor: true, ...data}, location.origin);
  function controls() {
    save.disabled = !config.canEdit || !ready || saving || uncertain || !(dirty() || config.canPublish && hasDraft);
    discard.disabled = saving || (!dirty() && !uncertain);
    root.querySelectorAll('[data-editor-mode]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.editorMode === mode));
      button.disabled = saving || button.dataset.editorMode === 'edit' && !config.canEdit;
    });
    root.setAttribute('aria-busy', String(saving));
    send({type: 'mode', editing: config.canEdit && ready && mode === 'edit' && !saving});
  }
  function showError(message) { error.textContent = message; error.hidden = false; }
  function clearChanges() {
    Object.values(blobs).forEach(url => URL.revokeObjectURL(url));
    changes = {}; files = {}; resets = new Set(); blobs = {}; uncertain = false;
  }
  async function loadPage(key, {force = false, message = ''} = {}) {
    if (!config.pages[key] || saving) return;
    if (!force && dirty() && !window.confirm('Discard unsaved changes and open another page?')) return;
    const request = ++loadVersion;
    clearChanges(); ready = false; page = key; loading.hidden = false; error.hidden = true;
    status.textContent = 'Loading page…'; controls();
    const url = new URL(location.href); url.searchParams.set('page', key); history.replaceState({}, '', url);
    try {
      const response = await fetch(config.pages[key].stateUrl, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('The page could not be loaded. Reload and check your access.');
      const state = await response.json(); if (request !== loadVersion) return;
      version = state.version; hasDraft = state.hasDraft;
      frame.src = config.pages[key].previewUrl;
      frame.dataset.loadedMessage = message || (state.hasDraft ? 'Private draft loaded' : 'All changes saved');
    } catch (failure) { if (request === loadVersion) { loading.hidden = true; showError(failure.message); status.textContent = 'Page unavailable'; } }
  }
  on(root, 'click', event => {
    const modeButton = event.target.closest('[data-editor-mode]');
    if (modeButton && !modeButton.disabled) { mode = modeButton.dataset.editorMode; controls(); }
  });
  on(discard, 'click', () => {
    if (window.confirm('Discard these unsaved changes and reload the saved page?')) loadPage(page, {force: true});
  });
  on(frame, 'load', () => {
    if (!frame.contentDocument?.querySelector('script[data-portal-page]')) {
      ready = false; loading.hidden = true; controls();
      showError('The page preview could not be loaded. Reload and check your access.');
      status.textContent = 'Preview unavailable';
    }
  });
  on(window, 'message', event => {
    if (event.source !== frame.contentWindow || event.origin !== location.origin || !event.data?.portalEditor) return;
    const data = event.data;
    if (data.page !== page) return;
    if (data.type === 'ready') { ready = true; loading.hidden = true; status.textContent = frame.dataset.loadedMessage || 'All changes saved'; controls(); }
    if (data.type === 'change' && config.canEdit && ready && !saving) {
      if (data.value === data.original) delete changes[data.field]; else changes[data.field] = data.value;
      resets.delete(data.field); status.textContent = dirty() ? 'Unsaved changes' : 'All changes saved'; controls();
    }
    if (data.type === 'picture' && config.canEdit && ready && !saving) {
      chosenHasImage = data.hasImage;
      chosenPicture = data.field; fileInput.value = ''; altInput.value = changes[data.field + '_alt'] ?? data.alt;
      root.querySelector('[data-picture-label]').textContent = data.label;
      root.querySelector('[data-picture-error]').textContent = ''; pictureDialog.showModal();
    }
    if (data.type === 'navigate') {
      const key = Object.keys(config.pages).find(key => config.pages[key].publicUrl === data.url);
      if (key) loadPage(key);
      else status.textContent = 'Choose another page using the navigation inside the preview.';
    }
    if (data.type === 'notice') status.textContent = data.message;
  });
  on(root.querySelector('[data-picture-apply]'), 'click', () => {
    const file = fileInput.files[0];
    if (!file && !files[chosenPicture] && !chosenHasImage) {
      root.querySelector('[data-picture-error]').textContent = 'Choose a picture to add to this page.'; return;
    }
    if (file && (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 5 * 1024 * 1024)) {
      root.querySelector('[data-picture-error]').textContent = 'Choose a PNG or JPEG image no larger than 5 MB.'; return;
    }
    if (file) {
      files[chosenPicture] = file;
      if (blobs[chosenPicture]) URL.revokeObjectURL(blobs[chosenPicture]);
      blobs[chosenPicture] = URL.createObjectURL(file);
    }
    changes[chosenPicture + '_alt'] = altInput.value;
    resets.delete(chosenPicture); resets.delete(chosenPicture + '_alt');
    send({type: 'picture-preview', field: chosenPicture, url: blobs[chosenPicture], alt: altInput.value});
    pictureDialog.close(); status.textContent = 'Unsaved changes'; controls();
  });
  on(root.querySelector('[data-picture-reset]'), 'click', () => {
    delete files[chosenPicture]; delete changes[chosenPicture + '_alt'];
    resets.add(chosenPicture); resets.add(chosenPicture + '_alt');
    send({type: 'picture-preview', field: chosenPicture, reset: true});
    pictureDialog.close(); status.textContent = 'Unsaved changes'; controls();
  });
  on(save, 'click', async () => {
    if (save.disabled) return;
    const finish = window.ActionFeedback?.start(save, {button: save, label: 'Saving page…'});
    saving = true; error.hidden = true; status.textContent = 'Saving…'; controls();
    const data = new FormData();
    data.set('csrfmiddlewaretoken', root.querySelector('[name=csrfmiddlewaretoken]').value);
    data.set('version', String(version)); data.set('changes', JSON.stringify(changes)); data.set('reset', JSON.stringify([...resets]));
    Object.entries(files).forEach(([key, file]) => data.set(key, file));
    let result;
    try {
      const response = await fetch(config.pages[page].saveUrl, {method: 'POST', credentials: 'same-origin', body: data});
      result = await response.json();
      if (!response.ok) { showError(result.error || 'Your access may have changed. Reload before saving.'); status.textContent = 'Changes not saved'; return; }
      version = result.version; clearChanges();
    } catch (_) {
      uncertain = true; showError('The save could not be confirmed. Reload the page to check the saved version before trying again.'); status.textContent = 'Check saved version';
    } finally { finish?.(); saving = false; controls(); }
    if (result?.version) loadPage(page, {force: true, message: result.message});
  });
  on(window, 'beforeunload', event => { if (dirty() || saving) { event.preventDefault(); event.returnValue = ''; } });
  cleanup(() => { loadVersion++; Object.values(blobs).forEach(url => URL.revokeObjectURL(url)); });
  loadPage(page, {force: true});
});
