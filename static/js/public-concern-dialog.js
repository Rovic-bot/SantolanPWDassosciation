/* Program tracking keeps its dialog; Community Assistance uses full pages. */
(() => {
  'use strict';
  if (document.querySelector('script[data-portal-page]')) return;
  document.querySelectorAll('[data-tracking-dialog]').forEach(dialog => {
    if (!dialog.showModal) return;
    const tracking = dialog.hasAttribute('data-tracking-dialog');
    const openSelector = tracking ? '[data-tracking-open]' : '[data-concern-open]';
    const body = dialog.querySelector('[data-concern-body]');
    const notice = dialog.querySelector('[data-concern-notice]');
    const progress = dialog.querySelector('[data-concern-progress]');
    const retry = dialog.querySelector('[data-concern-retry]');
    const paths = new Set(['verifyUrl', 'applyUrl', 'receiptUrl', 'finishUrl', 'conversationVerifyUrl', 'conversationUrl', 'conversationStartUrl'].map(key => dialog.dataset[key]).filter(Boolean));
    let opener, busy = false, loaded = false, retryURL = dialog.dataset.verifyUrl, controller;
    const localStep = value => {
      const url = new URL(value, location.href);
      return url.origin === location.origin && paths.has(url.pathname);
    };
    async function load(url, form) {
      if (busy || !localStep(url)) return;
      // Construct FormData before disabling controls; the shared CSRF listener keeps its token current.
      const data = form ? new FormData(form) : null;
      const finish = form && window.ActionFeedback?.start(form);
      const controls = [...body.querySelectorAll('button, input[type=submit]')].filter(el => !el.disabled);
      controls.forEach(el => { el.disabled = true; });
      busy = true;
      body.setAttribute('aria-busy', 'true');
      notice.hidden = true;
      progress.textContent = form ? 'Processing your request.' : 'Loading the form.';
      const request = new AbortController();
      controller = request;
      try {
        const response = await fetch(url, { method: form ? 'POST' : 'GET', body: data, credentials: 'same-origin', cache: 'no-store', signal: request.signal });
        const destination = new URL(response.url);
        if (form && new URL(url, location.href).pathname === dialog.dataset.finishUrl && response.ok &&
            destination.origin === location.origin && destination.pathname === dialog.dataset.resourcesUrl) {
          loaded = false;
          body.replaceChildren();
          dialog.close();
          return;
        }
        if (!localStep(destination) || ![200, 400, 429, 503].includes(response.status)) throw new Error('unavailable');
        const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
        if (request.signal.aborted) return;
        const main = parsed.querySelector('main#main-content');
        if (!main) throw new Error('unavailable');
        // DOMParser treats noscript as markup; its fallback CSS must not affect this live dialog.
        main.querySelectorAll('script, noscript').forEach(node => node.remove());
        // Forms without an explicit action must submit to their fetched step, not Resources.
        main.querySelectorAll('form').forEach(item => { item.action = new URL(item.getAttribute('action') || destination.href, destination.href).href; });
        body.replaceChildren(...main.childNodes);
        document.dispatchEvent(new CustomEvent('public:concern-loaded'));
        loaded = true;
        progress.textContent = body.querySelector('.errorlist') || [400, 429].includes(response.status) ? 'Please review the form errors.' : 'Form loaded.';
        if (dialog.open) {
          dialog.scrollTop = 0;
          const focus = body.querySelector('.errorlist, h1');
          if (focus) { focus.tabIndex = -1; focus.focus({ preventScroll: true }); }
        }
      } catch (error) {
        if (request.signal.aborted || error.name === 'AbortError') return;
        notice.hidden = false;
        retryURL = form ? (body.querySelector('[data-referral-conversation]') ? dialog.dataset.conversationUrl : dialog.dataset.applyUrl) : url;
        dialog.querySelector('[data-concern-error]').textContent = tracking ?
          'The application check could not be loaded. Please try again.' : form ?
          'We could not load the response. Check your request before submitting again.' :
          'The form could not be loaded. Please try again.';
        retry.textContent = form ? (tracking ? 'Check status' : 'Check request') : 'Try again';
        progress.textContent = '';
      } finally {
        finish?.();
        controls.forEach(el => { el.disabled = false; });
        if (controller === request) {
          busy = false;
          body.removeAttribute('aria-busy');
        }
      }
    }
    const markLinks = () => document.querySelectorAll(openSelector).forEach(link => link.setAttribute('aria-haspopup', 'dialog'));
    markLinks();
    document.addEventListener('public:results-updated', markLinks);
    document.addEventListener('click', event => {
        const link = event.target.closest(openSelector);
        if (!link || event.defaultPrevented) return;
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        opener = link;
        dialog.showModal();
        if (!loaded) load(link.href);
    });
    body.addEventListener('submit', event => {
      if (event.defaultPrevented) return;
      const form = event.target;
      if (form.method.toLowerCase() !== 'post' || !localStep(form.action)) return;
      event.preventDefault();
      load(form.action, form);
    });
    body.addEventListener('click', event => {
      if (event.defaultPrevented) return;
      const link = event.target.closest('a[href]');
      if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const url = new URL(link.href);
      if (localStep(url)) { event.preventDefault(); load(url); }
      else if (url.origin === location.origin && url.pathname === location.pathname) { event.preventDefault(); dialog.close(); }
    });
    retry.addEventListener('click', () => load(retryURL));
    // Preserve an unfinished concern, but remove private tracking details when closed.
    dialog.addEventListener('close', () => {
      if (tracking || body.querySelector('[data-referral-conversation], [data-conversation-finished]')) {
        controller?.abort();
        controller = null;
        busy = false;
        loaded = false;
        body.replaceChildren();
        body.removeAttribute('aria-busy');
      }
      opener?.focus({ preventScroll: true });
    });
    dialog.addEventListener('click', event => {
      const box = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) dialog.close();
    });
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const controls = [...dialog.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')].filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length);
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    });
  });
})();
