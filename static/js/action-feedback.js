/* Immediate pending feedback. Saved data and delivery results remain server-owned. */
'use strict';
WorkspacePage.run(({on, fetch, cleanup, setTimeout}) => {
  const active = new Map(), submissions = new WeakMap();
  const isSubmit = node => node instanceof HTMLButtonElement ? node.type === 'submit' :
    node instanceof HTMLInputElement && ['submit', 'image'].includes(node.type);
  const buttons = form => [...(form.elements || form.querySelectorAll('button, input'))].filter(isSubmit);
  const restoreAttribute = (node, name, value) => value == null ? node.removeAttribute(name) : node.setAttribute(name, value);
  const snapshot = node => ({node, children: [...node.childNodes], disabled: node.disabled,
    label: node.getAttribute('aria-label'), busy: node.getAttribute('aria-busy'),
    unavailable: node.getAttribute('aria-disabled')});

  function description(form, button) {
    if (button?.dataset.processingLabel || form.dataset.processingLabel) {
      return button?.dataset.processingLabel || form.dataset.processingLabel;
    }
    const text = (button?.textContent || button?.value || '').trim().toLowerCase();
    const action = `${form.getAttribute('action') || ''} ${form.elements?.namedItem('action')?.value || ''}`.toLowerCase();
    if (/ranking/.test(text) || /ewaf/.test(action) && /generate/.test(action)) return 'Generating ranking…';
    if (/generat.*certificate/.test(text)) return 'Generating certificate…';
    if (/test.*(email|connection)|check.*connection/.test(text)) return 'Checking email connection…';
    if (/email/.test(text) || /email.*retry|retry.*email/.test(action)) return 'Sending email…';
    if (/sign in|log in/.test(text)) return 'Signing in…';
    if (/undo|unrecord/.test(text)) return 'Undoing receipt…';
    if (/record.*receipt/.test(text)) return 'Recording receipt…';
    if (/unpublish/.test(text)) return 'Returning to draft…';
    if (/publish/.test(text)) return 'Publishing…';
    if (/archive/.test(text)) return 'Archiving…';
    if (/upload/.test(text)) return 'Uploading…';
    if (/send/.test(text)) return 'Sending…';
    if (/calculat/.test(text)) return 'Calculating…';
    if (form.getAttribute('method')?.toLowerCase() === 'get') return 'Loading results…';
    if (/save|update|approve|eligible|confirm|record/.test(text)) return 'Saving…';
    return 'Processing…';
  }

  function start(form, {button, label, message, native = false} = {}) {
    if (!form) return () => {};
    if (active.has(form)) return active.get(form).acquire();
    const submitted = submissions.get(form);
    button ||= submitted?.button || buttons(form).find(node => !node.disabled);
    const saved = submitted?.controls || buttons(form).map(snapshot);
    const original = saved.find(item => item.node === button) || (button && snapshot(button));
    if (original && !saved.includes(original)) saved.push(original);
    const busy = submitted ? submitted.busy : form.getAttribute('aria-busy');
    label ||= description(form, button);
    const notice = document.createElement('p'), announcement = document.createElement('span');
    notice.className = 'action-progress';
    announcement.className = 'action-announcement'; announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite'); announcement.setAttribute('aria-atomic', 'true');
    // Keep the visible message inside a form's grid cell. A separate, visually
    // hidden live region sits outside aria-busy without moving adjacent panels.
    if (form instanceof HTMLFormElement) form.append(notice);
    else form.insertAdjacentElement('afterend', notice);
    form.insertAdjacentElement('afterend', announcement);
    notice.textContent = announcement.textContent = message || form.dataset.processingMessage || `${label} Please wait.`;
    form.setAttribute('aria-busy', 'true');
    saved.forEach(({node}) => node.setAttribute('aria-disabled', 'true'));
    if (button) {
      button.classList.add('is-processing');
      button.setAttribute('aria-busy', 'true'); button.setAttribute('aria-label', label);
      if (!(button instanceof HTMLInputElement)) {
        const spinner = document.createElement('span'), caption = document.createElement('span');
        spinner.className = 'action-spinner'; spinner.setAttribute('aria-hidden', 'true');
        caption.textContent = label;
        // Retain the actual original nodes, including their event listeners.
        button.replaceChildren(spinner, caption);
      }
    }
    let ended = false;
    const finish = ({restoreDisabled = false} = {}) => {
      if (ended) return;
      ended = true; active.delete(form); submissions.delete(form); notice.remove(); announcement.remove();
      restoreAttribute(form, 'aria-busy', busy);
      saved.forEach(item => {
        restoreAttribute(item.node, 'aria-disabled', item.unavailable);
        if (restoreDisabled) item.node.disabled = item.disabled;
      });
      if (original) {
        const node = original.node;
        node.classList.remove('is-processing');
        restoreAttribute(node, 'aria-busy', original.busy);
        restoreAttribute(node, 'aria-label', original.label);
        if (!(node instanceof HTMLInputElement)) node.replaceChildren(...original.children);
      }
    };
    let requests = 0;
    const acquire = () => {
      requests++;
      let released = false;
      return options => {
        if (released || ended) return;
        released = true;
        if (--requests === 0) finish(options);
      };
    };
    active.set(form, {finish, native, acquire});
    setTimeout(() => {
      if (!ended) notice.textContent = announcement.textContent = `${label} This is taking longer than usual. Keep this page open; the request is still pending.`;
    }, 15000);
    return acquire();
  }

  on(document, 'click', event => {
    const button = event.target.closest('button, input[type=submit], input[type=image], a.is-processing');
    if (button && (button.classList.contains('is-processing') || isSubmit(button) && active.has(button.form))) {
      event.preventDefault(); event.stopImmediatePropagation();
    }
  }, true);
  on(document, 'submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (active.has(form)) { event.preventDefault(); event.stopImmediatePropagation(); return; }
    const submitted = {button: event.submitter, controls: buttons(form).map(snapshot), busy: form.getAttribute('aria-busy')};
    submissions.set(form, submitted);
    setTimeout(() => { if (!active.has(form) && submissions.get(form) === submitted) submissions.delete(form); }, 0);
  }, true);
  // Run after validation and page-specific submit handlers. Never turn a rejected
  // form, cancelled confirmation, or AJAX request into a second native submission.
  on(window, 'submit', event => {
    const form = event.target;
    if (event.defaultPrevented || !(form instanceof HTMLFormElement) || active.has(form) ||
        form.hasAttribute('data-processing-skip') || form.method.toLowerCase() === 'dialog') return;
    const target = event.submitter?.getAttribute('formtarget') || form.getAttribute('target');
    if (target && target !== '_self') return;
    const action = new URL(event.submitter?.getAttribute('formaction') || form.getAttribute('action') || location.href, location.href);
    if (action.origin !== location.origin) return;
    // Downloads keep the current page; their own controller owns completion.
    if (/\/(export|download)(\/|\.|$)/.test(action.pathname)) return;
    start(form, {native: true});
  });
  on(window, 'pageshow', () => {
    [...active.values()].filter(item => item.native).forEach(item => item.finish({restoreDisabled: true}));
  });
  on(document, 'click', async event => {
    const link = event.target.closest('[data-processing-download], .member-report-exports a');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || (link.target && link.target !== '_self')) return;
    event.preventDefault();
    const finish = start(link, {button: link, label: 'Preparing download…'});
    link.parentElement.querySelector('[data-download-feedback]')?.remove();
    let message;
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
      const disposition = response.headers.get('content-disposition') || '';
      if (!response.ok || !/^attachment\b/i.test(disposition)) throw new Error('unavailable');
      const blob = await response.blob();
      const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const plain = disposition.match(/filename="([^"]+)"|filename=([^;]+)/i);
      const name = (encoded ? decodeURIComponent(encoded) : plain?.[1] || plain?.[2] || 'download').replace(/[\\/:*?"<>|\x00-\x1f]/g, '_');
      const download = document.createElement('a'), objectURL = URL.createObjectURL(blob);
      download.href = objectURL; download.download = name;
      document.body.append(download); download.click(); download.remove();
      setTimeout(() => URL.revokeObjectURL(objectURL), 1000);
      cleanup(() => URL.revokeObjectURL(objectURL));
      message = 'File prepared. Your browser will handle the download.';
    } catch (error) {
      if (error.name !== 'AbortError') message = 'Download could not be prepared. Check your connection and access, then try again.';
    } finally { finish(); }
    if (message && link.isConnected) {
      const notice = document.createElement('p');
      notice.className = 'action-progress'; notice.dataset.downloadFeedback = '';
      notice.setAttribute('role', 'status'); notice.textContent = message;
      link.insertAdjacentElement('afterend', notice);
    }
  });
  const api = {start, pending: form => active.has(form)};
  window.ActionFeedback = api;
  cleanup(() => {
    [...active.values()].forEach(item => item.finish());
    if (window.ActionFeedback === api) delete window.ActionFeedback;
  });
});
