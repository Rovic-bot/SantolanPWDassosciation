/* Progressive admin tabs: request fresh, permission-checked HTML; retain scroll. */
(() => {
  'use strict';
  if (!document.body.classList.contains('admin-workspace') || document.body.classList.contains('native-admin-workspace')) return;
  const selector = '.workspace-module-links a, .workspace-brand, [data-workspace-tab], ' +
    'main nav a, .registration-inbox-clear';
  const persistent = /\/(workspace-page|workspace-navigation)\.js$/;
  const bootstrap = /\/vendor\/bootstrap\/bootstrap\.bundle\.min\.js$/;
  let pending, queued, sequence = 0, committing = false, renderedPath = location.pathname;
  history.scrollRestoration = 'manual';
  const scroll = () => ({x: scrollX, y: scrollY});
  function savePosition() {
    history.replaceState({...history.state, workspaceNavigation: true, workspaceScroll: scroll()}, '', location.href);
  }
  savePosition();

  function status(message, error = false) {
    let node = document.getElementById('workspace-navigation-status');
    if (!node) {
      node = document.createElement('div');
      node.id = 'workspace-navigation-status';
      node.setAttribute('role', 'status');
      document.body.append(node);
    }
    node.className = error ? 'workspace-navigation-error' : 'visually-hidden';
    node.textContent = message;
  }
  function eligible(link) {
    if (!link || link.download || (link.target && link.target !== '_self')) return false;
    const url = new URL(link.href, location.href);
    // Native Django administration and public pages retain their own navigation lifecycle.
    const nativeAdmin = url.pathname.startsWith('/admin/') &&
      !/^\/admin\/(members|programs|events|applications|ewaf)\/?$/.test(url.pathname);
    return url.origin === location.origin && !nativeAdmin && !url.hash;
  }
  function executable(script) {
    return !script.type || ['text/javascript', 'application/javascript', 'module'].includes(script.type);
  }
  async function prepareStyles(page) {
    const old = [...document.head.querySelectorAll('link[rel=stylesheet], style')];
    const desired = [...page.head.querySelectorAll('link[rel=stylesheet], style')];
    const retained = new Set(), staged = [], ordered = [];
    try {
      await Promise.all(desired.map(async (original, index) => {
        const existing = old.find(node => original.tagName === 'LINK' && node.href === original.href);
        if (existing) { retained.add(existing); ordered[index] = existing; return; }
        const node = document.importNode(original, true), media = node.media;
        ordered[index] = node;
        node.media = 'not all';
        staged.push({node, media});
        const loaded = node.tagName === 'LINK' ? new Promise((resolve, reject) => {
          node.onload = resolve; node.onerror = () => reject(new Error('Unable to load this tab’s styles.'));
        }) : Promise.resolve();
        document.head.append(node);
        await loaded;
      }));
      return {
        apply() {
          staged.forEach(({node, media}) => { node.media = media; });
          old.forEach(node => { if (!retained.has(node)) node.remove(); });
          ordered.forEach(node => document.head.append(node));
        },
        discard() { staged.forEach(({node}) => node.remove()); }
      };
    } catch (error) { staged.forEach(({node}) => node.remove()); throw error; }
  }
  function loadScript(original) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = original.src;
      script.async = false;
      script.dataset.workspaceScript = '';
      script.onload = resolve;
      script.onerror = () => reject(new Error('Unable to initialize this tab. Refresh to try again.'));
      document.head.append(script);
    });
  }
  async function navigate(href, {pop = false, position = scroll(), focus = null} = {}) {
    if (committing) { queued = {href, options: {pop, position, focus}}; return; }
    if (!pop && !WorkspacePage.canLeave()) return;
    const id = ++sequence;
    pending?.abort();
    pending = new AbortController();
    status('Opening tab…');
    document.getElementById('main-content')?.setAttribute('aria-busy', 'true');
    let styles;
    try {
      await WorkspacePage.settle();
      if (id !== sequence) return;
      const response = await fetch(href, {credentials: 'same-origin', cache: 'no-store', signal: pending.signal});
      if (id !== sequence) return;
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      // DOMParser parses noscript children with scripting disabled. Importing
      // those nodes would activate fallback styles in this JavaScript session.
      page.querySelectorAll('noscript').forEach(node => node.remove());
      if (id !== sequence) return;
      if (!response.ok || !page.body.classList.contains('admin-workspace') ||
          page.body.classList.contains('native-admin-workspace') || !page.getElementById('main-content')) {
        // Authentication, access-denied and unsupported routes use their normal server response.
        location.assign(response.url || href);
        return;
      }
      const scripts = [...page.querySelectorAll('script')].filter(executable);
      if (scripts.some(script => !script.src || new URL(script.src).origin !== location.origin)) {
        location.assign(response.url || href);
        return;
      }
      // A page can update its own read-only content without rebuilding the shell.
      const update = {page, url: new URL(response.url || href, location.href), render: null};
      document.dispatchEvent(new CustomEvent('workspace:render', {detail: update}));
      if (typeof update.render === 'function') {
        committing = true;
        if (!pop) savePosition();
        update.render();
        document.title = page.title;
        if (!pop) history.pushState({workspaceNavigation: true, workspaceScroll: position}, '', update.url.pathname + update.url.search);
        renderedPath = update.url.pathname;
        if (focus) document.getElementById(focus.id)?.focus({preventScroll: true});
        window.scrollTo({left: position.x, top: position.y, behavior: 'instant'});
        status('Details updated.');
        document.dispatchEvent(new CustomEvent('workspace:navigated', {detail: {partial: true}}));
        return;
      }
      styles = await prepareStyles(page);
      if (id !== sequence) { styles.discard(); return; }
      committing = true;
      if (!pop) savePosition();
      WorkspacePage.replace();
      document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
      document.head.querySelectorAll('script').forEach(script => {
        if (!persistent.test(new URL(script.src || location.href).pathname)) script.remove();
      });
      page.querySelectorAll('script').forEach(script => { if (executable(script)) script.remove(); });
      // Hold enough height during replacement to avoid an intermediate jump to zero.
      document.documentElement.style.minHeight = `${position.y + innerHeight}px`;
      document.documentElement.classList.remove('dashboard-modal-open', 'ewaf-enhanced',
        'ewaf-dialog-open', 'program-dialog-open', 'record-dialog-open');
      document.body.className = page.body.className;
      document.body.replaceChildren(...[...page.body.childNodes].map(node => document.importNode(node, true)));
      document.getElementById('main-content')?.setAttribute('aria-busy', 'true');
      styles.apply();
      document.title = page.title;
      const target = new URL(response.url || href);
      if (!pop) history.pushState({workspaceNavigation: true, workspaceScroll: position}, '', target.pathname + target.search);
      renderedPath = target.pathname;
      for (const script of scripts) {
        const pathname = new URL(script.src).pathname;
        if (!persistent.test(pathname) && !bootstrap.test(pathname)) await loadScript(script);
      }
      WorkspacePage.show();
      if (focus) {
        const control = document.getElementById(focus.id);
        control?.focus({preventScroll: true});
        if (control?.setSelectionRange && focus.start != null) control.setSelectionRange(focus.start, focus.end);
      } else document.getElementById('main-content')?.focus({preventScroll: true});
      await new Promise(requestAnimationFrame);
      document.documentElement.style.minHeight = '';
      window.scrollTo({left: position.x, top: position.y, behavior: 'instant'});
      status(`${page.title.split('·')[0].trim()} opened.`);
      document.dispatchEvent(new CustomEvent('workspace:navigated'));
    } catch (error) {
      if (error.name !== 'AbortError' && id === sequence) status(error.message || 'Unable to open this tab. Please try again.', true);
    } finally {
      if (id === sequence) {
        committing = false;
        document.documentElement.style.minHeight = '';
        document.getElementById('main-content')?.removeAttribute('aria-busy');
        if (queued) {
          const next = queued; queued = null;
          navigate(next.href, next.options);
        }
      }
    }
  }
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest(selector);
    if (!eligible(link)) return;
    event.preventDefault();
    navigate(link.href);
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if (event.defaultPrevented || !form.matches('form[data-auto-filter]') || form.method.toLowerCase() !== 'get') return;
    const url = new URL(form.action || location.href);
    if (url.origin !== location.origin) return;
    event.preventDefault();
    url.search = new URLSearchParams(new FormData(form, event.submitter)).toString();
    const input = document.activeElement;
    navigate(url.href, {focus: input?.form === form ? {id: input.id, start: input.selectionStart, end: input.selectionEnd} : null});
  });
  addEventListener('popstate', event => {
    if (location.pathname === renderedPath && !event.state?.workspaceNavigation) return;
    event.stopImmediatePropagation();
    navigate(location.href, {pop: true, position: event.state?.workspaceScroll || scroll()});
  }, true);
})();
