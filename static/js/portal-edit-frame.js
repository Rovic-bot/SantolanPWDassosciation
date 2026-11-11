(() => {
  'use strict';
  if (window.parent === window) return;
  const page = document.currentScript.dataset.portalPage;
  const send = payload => parent.postMessage({portalEditor: true, page, ...payload}, location.origin);
  const fields = [...document.querySelectorAll('[data-portal-field]')];
  const pictures = [...document.querySelectorAll('[data-portal-picture]')];
  let editing = false;
  fields.forEach(field => {
    field.dataset.originalText = field.innerText;
    field.setAttribute('spellcheck', 'true');
    field.setAttribute('aria-label', field.dataset.portalLabel);
  });
  pictures.forEach(picture => {
    picture.portalOriginal = picture.querySelector('[data-portal-original]').innerHTML;
    picture.dataset.empty = String(!picture.querySelector('img,svg'));
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'portal-picture-action'; button.textContent = 'Change picture';
    button.addEventListener('click', () => send({type: 'picture', field: picture.dataset.portalPicture,
      label: picture.dataset.portalLabel, hasImage: Boolean(picture.querySelector('img')), alt: picture.querySelector('img')?.alt || ''}));
    picture.append(button);
    picture.addEventListener('click', event => {
      if (editing && event.target instanceof HTMLImageElement) button.click();
    });
  });
  function setMode(enabled) {
    editing = enabled; document.body.dataset.portalEditing = String(enabled);
    fields.forEach(field => {
      field.contentEditable = enabled ? 'plaintext-only' : 'false';
      if (enabled) { field.tabIndex = 0; field.setAttribute('role', 'textbox'); field.setAttribute('aria-multiline', 'true'); }
      else { field.removeAttribute('tabindex'); field.removeAttribute('role'); field.removeAttribute('aria-multiline'); }
    });
  }
  document.addEventListener('input', event => {
    const field = event.target.closest('[data-portal-field]');
    if (!editing || !field) return;
    fields.filter(other => other !== field && other.dataset.portalField === field.dataset.portalField)
      .forEach(other => { other.textContent = field.innerText; });
    send({type: 'change', field: field.dataset.portalField, value: field.innerText,
      original: field.dataset.originalText});
  });
  document.addEventListener('paste', event => {
    if (!editing || !event.target.closest('[data-portal-field]')) return;
    event.preventDefault();
    const selection = window.getSelection();
    if (!selection.rangeCount) return;
    const range = selection.getRangeAt(0); range.deleteContents();
    const text = document.createTextNode(event.clipboardData.getData('text/plain'));
    range.insertNode(text); range.setStartAfter(text); range.collapse(true);
    selection.removeAllRanges(); selection.addRange(range);
    event.target.dispatchEvent(new Event('input', {bubbles: true}));
  });
  document.addEventListener('submit', event => { event.preventDefault(); send({type: 'notice', message: 'Forms are inactive in the page editor.'}); }, true);
  document.addEventListener('click', event => {
    const anchor = event.target.closest('a[href]');
    if (!anchor || event.target.closest('[data-portal-field]') && editing) { if (anchor && editing) event.preventDefault(); return; }
    const url = new URL(anchor.href);
    if (anchor.getAttribute('href').startsWith('#')) return;
    event.preventDefault();
    send({type: 'navigate', url: url.pathname, hash: url.hash});
  }, true);
  window.addEventListener('message', event => {
    if (event.source !== parent || event.origin !== location.origin || !event.data?.portalEditor) return;
    const data = event.data;
    if (data.type === 'mode') setMode(data.editing === true);
    if (data.type === 'picture-preview') {
      const picture = pictures.find(item => item.dataset.portalPicture === data.field);
      if (!picture) return;
      const button = picture.querySelector('.portal-picture-action');
      if (data.reset) {
        picture.innerHTML = picture.portalOriginal; picture.append(button);
      } else {
        picture.querySelectorAll('source').forEach(source => source.remove());
        let img = picture.querySelector('img');
        if (!img) {
          picture.replaceChildren(button);
          const figure = document.createElement('figure'); figure.className = 'portal-custom-picture';
          img = document.createElement('img'); figure.append(img); picture.prepend(figure);
        }
        if (data.url && data.url.startsWith('blob:')) img.src = data.url;
        img.removeAttribute('srcset'); img.alt = data.alt || '';
      }
      picture.dataset.empty = String(!picture.querySelector('img,svg'));
    }
  });
  send({type: 'ready'});
})();
