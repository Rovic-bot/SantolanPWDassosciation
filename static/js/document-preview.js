/* Authorized, bounded attachment previews without leaving the applicant page. */
WorkspacePage.run(api => {
  'use strict';
  const {on, cleanup, fetch} = api;
  const dialog = document.querySelector('[data-document-preview-dialog]');
  if (!dialog?.showModal) return;
  const title = dialog.querySelector('[data-document-preview-title]');
  const content = dialog.querySelector('[data-document-preview-content]');
  const viewer = dialog.querySelector('[data-document-preview-viewer]');
  const status = dialog.querySelector('[data-document-preview-status]');
  const help = dialog.querySelector('[data-document-preview-help]');
  const download = dialog.querySelector('[data-document-preview-download]');
  const retry = dialog.querySelector('[data-document-preview-retry]');
  const close = dialog.querySelector('[data-document-preview-close]');
  const MAX_BYTES = 20 * 1024 * 1024;
  const signatures = {
    'application/pdf': [37, 80, 68, 70, 45],
    'image/png': [137, 80, 78, 71, 13, 10, 26, 10],
    'image/jpeg': [255, 216, 255],
  };
  let opener, source, pending, objectURL, generation = 0, restoreFocus = true;
  const clear = () => {
    generation++;
    pending?.abort(); pending = null;
    viewer.replaceChildren();
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = null;
    content.setAttribute('aria-busy', 'false');
  };
  const failure = message => {
    viewer.replaceChildren();
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = null;
    content.setAttribute('aria-busy', 'false');
    status.textContent = message;
    status.setAttribute('data-error', '');
    retry.hidden = false;
  };
  async function boundedBlob(response, type) {
    const declared = Number(response.headers.get('Content-Length'));
    if (declared > MAX_BYTES) throw new Error('size');
    if (!response.body?.getReader) throw new Error('unsupported');
    const reader = response.body.getReader(), chunks = [];
    let size = 0;
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > MAX_BYTES) { await reader.cancel(); throw new Error('size'); }
        chunks.push(part.value);
      }
    } finally { reader.releaseLock(); }
    if (!size) throw new Error('empty');
    const blob = new Blob(chunks, {type});
    const header = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
    if (!signatures[type].every((byte, index) => header[index] === byte)) throw new Error('type');
    return blob;
  }
  async function load() {
    clear();
    const token = generation, request = new AbortController();
    pending = request;
    retry.hidden = true;
    status.removeAttribute('data-error');
    status.textContent = 'Loading document preview…';
    help.textContent = 'Download a copy if you need to view it separately.';
    content.setAttribute('aria-busy', 'true');
    const timeout = window.setTimeout(() => request.abort(), 30000);
    try {
      const response = await fetch(source.href, {credentials: 'same-origin', cache: 'no-store',
        redirect: 'error', signal: request.signal, headers: {'Accept': 'application/pdf,image/png,image/jpeg'}});
      if (!response.ok) throw new Error(response.status === 403 || response.status === 401 ? 'access' : 'response');
      const type = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
      if (!Object.hasOwn(signatures, type)) throw new Error('type');
      const blob = await boundedBlob(response, type);
      if (token !== generation || !dialog.open || request.signal.aborted) return;
      if (type === 'application/pdf' && navigator.pdfViewerEnabled === false) throw new Error('unsupported');
      objectURL = URL.createObjectURL(blob);
      const element = document.createElement(type === 'application/pdf' ? 'iframe' : 'img');
      if (type === 'application/pdf') {
        // Only signature-checked application/pdf blobs reach the native PDF
        // viewer. iframe sandbox flags block that viewer in Chromium; the
        // browser's PDF renderer supplies its own isolation. Never embed HTML.
        element.title = 'Preview of ' + title.textContent;
        element.referrerPolicy = 'no-referrer';
        help.textContent = 'If the preview is blank, download the document to view it.';
      } else {
        element.alt = title.textContent;
        element.addEventListener('error', () => {
          if (token === generation && dialog.open) failure('This image could not be displayed. Download the document to view it.');
        }, {once: true});
      }
      element.addEventListener('load', () => {
        if (token !== generation || !dialog.open) return;
        status.textContent = '';
        content.setAttribute('aria-busy', 'false');
      }, {once: true});
      element.src = objectURL;
      viewer.replaceChildren(element);
    } catch (error) {
      request.abort();
      if (token !== generation || !dialog.open) return;
      const messages = {
        access: 'You no longer have access to this document. Close the preview and reload the applicant page.',
        size: 'This document is too large for the popup preview. Download it to view the complete file.',
        type: 'This file cannot be previewed safely here. Download the document to view it.',
        unsupported: 'Your browser cannot display this document here. Download it to view the file.',
      };
      failure(messages[error.message] || 'The document could not be loaded. Try again, or close the preview and reload the applicant page.');
    } finally {
      window.clearTimeout(timeout);
      if (pending === request) pending = null;
    }
  }
  on(document, 'click', event => {
    const link = event.target.closest('a[data-document-preview]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol)) return;
    const downloadURL = new URL(link.dataset.downloadUrl || url.href, location.href);
    if (downloadURL.origin !== location.origin) return;
    downloadURL.searchParams.delete('preview');
    event.preventDefault();
    opener = link; source = url; restoreFocus = true;
    title.textContent = link.dataset.previewTitle || 'Submitted document';
    download.href = downloadURL.href;
    if (!dialog.open) dialog.showModal();
    document.documentElement.classList.add('document-preview-open');
    close.focus({preventScroll: true});
    load();
  });
  on(close, 'click', () => dialog.close());
  on(retry, 'click', load);
  on(dialog, 'keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('button:not(:disabled), a[href], iframe')]
      .filter(element => element.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  on(dialog, 'click', event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  on(dialog, 'close', () => {
    clear();
    document.documentElement.classList.remove('document-preview-open');
    download.removeAttribute('href');
    source = null;
    if (restoreFocus && opener?.isConnected) opener.focus({preventScroll: true});
  });
  const dispose = () => {
    restoreFocus = false;
    clear();
    if (dialog.open) dialog.close();
    document.documentElement.classList.remove('document-preview-open');
  };
  on(window, 'pagehide', dispose);
  cleanup(dispose);
});
