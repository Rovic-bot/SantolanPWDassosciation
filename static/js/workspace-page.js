/* Page-scoped resources for both normal loads and workspace tab navigation. */
(() => {
  'use strict';
  let current;
  function createPage() {
    const controller = new AbortController(), disposers = [], hides = [], shows = [], guards = [];
    const writes = new Set();
    let disposed = false;
    const cleanup = callback => disposers.push(callback);
    function on(target, type, callback, options) {
      if (target === document && type === 'DOMContentLoaded' && document.readyState !== 'loading') {
        if (!disposed) callback(new Event(type));
        return;
      }
      target.addEventListener(type, callback, options);
      cleanup(() => target.removeEventListener(type, callback, options));
      if (target === window) {
        if (type === 'pagehide') hides.push(callback);
        if (type === 'pageshow') shows.push(callback);
        if (type === 'beforeunload') guards.push(callback);
      }
    }
    const timers = new Set(), frames = new Set();
    function setTimeout(callback, delay, ...args) {
      const id = window.setTimeout(() => { timers.delete(id); if (!disposed) callback(...args); }, delay);
      timers.add(id);
      return id;
    }
    function requestAnimationFrame(callback) {
      const id = window.requestAnimationFrame(time => { frames.delete(id); if (!disposed) callback(time); });
      frames.add(id);
      return id;
    }
    function observer(Type) {
      if (!Type) return undefined;
      return class extends Type {
        constructor(callback, options) {
          super((...args) => { if (!disposed) callback(...args); }, options);
          cleanup(() => this.disconnect());
        }
      };
    }
    async function fetch(input, options = {}) {
      const request = new AbortController();
      const abort = () => request.abort();
      const signals = [controller.signal, options.signal || input?.signal].filter(Boolean);
      signals.forEach(signal => {
        if (signal.aborted) abort();
        else signal.addEventListener('abort', abort, {once: true});
      });
      const promise = window.fetch(input, {...options, signal: request.signal});
      if (!['GET', 'HEAD'].includes((options.method || input?.method || 'GET').toUpperCase())) writes.add(promise);
      try { return await promise; }
      finally {
        writes.delete(promise);
        // Keep the page's abort signal attached while a streamed body is read.
        cleanup(() => signals.forEach(signal => signal.removeEventListener('abort', abort)));
      }
    }
    return {
      api: {on, fetch, setTimeout, requestAnimationFrame, cleanup,
        ResizeObserver: observer(window.ResizeObserver), MutationObserver: observer(window.MutationObserver),
        IntersectionObserver: observer(window.IntersectionObserver),
        addEventListener: (...args) => on(window, ...args)},
      async settle() { await Promise.allSettled([...writes]); },
      canLeave() {
        const event = new Event('beforeunload', {cancelable: true});
        guards.forEach(callback => callback(event));
        return !event.defaultPrevented || window.confirm('Leave this page? Your unsaved changes may be lost.');
      },
      show() { shows.forEach(callback => callback(new PageTransitionEvent('pageshow'))); },
      destroy() {
        hides.forEach(callback => callback(new PageTransitionEvent('pagehide')));
        disposed = true;
        controller.abort();
        timers.forEach(id => window.clearTimeout(id));
        frames.forEach(id => window.cancelAnimationFrame(id));
        disposers.reverse().forEach(callback => callback());
      }
    };
  }
  current = createPage();
  window.WorkspacePage = {
    run: initialize => initialize(current.api),
    canLeave: () => current.canLeave(),
    settle: () => current.settle(),
    replace() { current.destroy(); current = createPage(); },
    show: () => current.show()
  };
})();
