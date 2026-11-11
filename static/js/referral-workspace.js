WorkspacePage.run(({on, ResizeObserver, requestAnimationFrame, cleanup}) => {
/* Native detail pages and the same protected content loaded into a dialog. */
(() => {
  const collapsedPanels = new Set();
  function initialize(root) {
    if (root.matches?.('[data-referral-closed]')) {
      root.closest('.record-details-dialog')?.close();
      return;
    }
    const ticket = root.matches?.('.referral-ticket') ? root : root.querySelector('.referral-ticket');
    const dialog = ticket?.closest('.record-details-dialog');
    if (dialog) dialog.setAttribute('aria-labelledby', 'referral-ticket-title');
    ticket?.querySelectorAll('[data-referral-member-photo]').forEach(photo => {
      if (photo.dataset.initialized) return;
      photo.dataset.initialized = 'true';
      const fallback = () => { photo.hidden = true; };
      photo.addEventListener('error', fallback, {once: true});
      if (photo.complete && !photo.naturalWidth) fallback();
    });
    const toggle = ticket?.querySelector('[data-referral-sidebar-toggle]');
    if (toggle && !toggle.dataset.initialized) {
      toggle.dataset.initialized = 'true';
      toggle.hidden = false;
      const panel = ticket.querySelector('#referral-sidebar-content');
      const grid = ticket.querySelector('.referral-ticket-grid');
      const key = ticket.dataset.referralTicket;
      const menu = ticket.querySelector('[data-referral-sidebar-menu]');
      const sidebar = ticket.querySelector('.referral-ticket-sidebar');
      const main = ticket.querySelector('.referral-ticket-main');
      const phone = window.matchMedia('(max-width: 899px)');
      const mobile = () => !!menu && phone.matches;
      let measuredWidth = -1, wasMobile = mobile();
      if (menu) menu.hidden = false;
      const backdrop = ticket.querySelector('.referral-panel-backdrop');
      if (backdrop) backdrop.hidden = false;
      function sizePanel() {
        const width = grid.clientWidth;
        if (!width || width === measuredWidth) return;
        measuredWidth = width;
        const panelWidth = mobile() ? Math.min(380, width - 16) : Math.max(290, width * 2 / 7);
        grid.style.setProperty('--referral-sidebar-width', panelWidth + 'px');
        grid.style.setProperty('--referral-sidebar-content-width', panelWidth + 'px');
      }
      function setCollapsed(collapsed, focus = false) {
        if (collapsed && panel.contains(document.activeElement)) (mobile() ? menu : toggle).focus({preventScroll: true});
        panel.inert = collapsed;
        panel.setAttribute('aria-hidden', String(collapsed));
        grid.classList.toggle('is-sidebar-collapsed', collapsed);
        main.inert = mobile() && !collapsed;
        toggle.setAttribute('aria-expanded', String(!collapsed));
        toggle.setAttribute('aria-label', collapsed ? 'Expand evidence and activity panel' : 'Collapse evidence and activity panel');
        toggle.title = collapsed ? 'Expand panel to the left' : 'Collapse panel to the right';
        toggle.querySelector('span').textContent = collapsed ? 'Show panel' : 'Hide panel';
        if (menu) {
          menu.setAttribute('aria-expanded', String(!collapsed));
          menu.setAttribute('aria-label', collapsed ? 'Open ticket details' : 'Close ticket details');
        }
        if (mobile() && !collapsed) {
          sidebar.setAttribute('role', 'dialog');
          sidebar.setAttribute('aria-modal', 'true');
          sidebar.setAttribute('aria-labelledby', 'referral-panel-title');
          if (focus) panel.querySelector('[data-referral-panel-dismiss]')?.focus({preventScroll: true});
        } else {
          sidebar.removeAttribute('role'); sidebar.removeAttribute('aria-modal'); sidebar.removeAttribute('aria-labelledby');
        }
        if (!mobile()) {
          if (collapsed) collapsedPanels.add(key); else collapsedPanels.delete(key);
        }
      }
      sizePanel();
      if (ResizeObserver) {
        const observer = new ResizeObserver(() => {
          if (!ticket.isConnected) { observer.disconnect(); return; }
          sizePanel();
        });
        observer.observe(grid);
      } else on(window, 'resize', sizePanel);
      on(phone, 'change', () => {
        measuredWidth = -1; sizePanel();
        if (wasMobile !== mobile()) {
          wasMobile = mobile();
          setCollapsed(mobile() || collapsedPanels.has(key));
        }
      });
      setCollapsed(mobile() || collapsedPanels.has(key));
      requestAnimationFrame(() => grid.classList.add('sidebar-ready'));
      on(toggle, 'click', () => setCollapsed(toggle.getAttribute('aria-expanded') === 'true'));
      if (menu) on(menu, 'click', () => setCollapsed(menu.getAttribute('aria-expanded') === 'true', true));
      ticket.querySelectorAll('[data-referral-panel-dismiss]').forEach(button => on(button, 'click', () => {
        setCollapsed(true); menu?.focus({preventScroll: true});
      }));
      on(ticket, 'keydown', event => {
        if (!mobile() || grid.classList.contains('is-sidebar-collapsed')) return;
        if (event.key === 'Escape') { event.preventDefault(); setCollapsed(true); menu.focus({preventScroll: true}); }
        if (event.key === 'Tab') {
          const items = [...panel.querySelectorAll('button, a[href], input, select, textarea, summary, [tabindex="0"]')].filter(node => !node.disabled && node.getClientRects().length);
          const first = items[0], last = items[items.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
      });
    }
    if (ticket && document.body.classList.contains('referral-chat-page') && window.visualViewport) {
      const fitViewport = () => document.body.style.setProperty('--referral-viewport-height', window.visualViewport.height + 'px');
      fitViewport(); on(window.visualViewport, 'resize', fitViewport);
      cleanup(() => document.body.style.removeProperty('--referral-viewport-height'));
    }
    const open = root.querySelector('[data-referral-open]');
    if (open) { open.requestSubmit(); return; }
    const form = root.querySelector('[data-referral-reply]');
    if (!form || form.dataset.initialized) return;
    form.dataset.initialized = 'true';
    const channel = form.elements.namedItem('channel');
    function update() {
      const email = channel.value === 'email';
      (form.querySelector('[data-reply-submit-label]') || form.querySelector('[data-reply-submit]')).textContent = channel.value === 'email'
        ? 'Send email' : 'Send to conversation';
      form.querySelector('[data-email-addresses]').hidden = !email;
      form.querySelector('[data-online-destination]').hidden = email;
      const connectionNotice = ticket?.querySelector('[data-email-connection-notice]');
      if (connectionNotice) connectionNotice.hidden = !email;
    }
    channel.addEventListener('change', update);
    update();
  }
  initialize(document);
  on(document, 'record-details:loaded', event => initialize(event.detail.root));
  on(document, 'record-details:closed', () => {
    document.querySelector('#record-details-dialog')?.setAttribute('aria-labelledby', 'record-dialog-heading');
  });
  on(document, 'click', event => {
    const close = event.target.closest('[data-referral-close]');
    const dialog = close?.closest('.record-details-dialog');
    if (!dialog || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); dialog.close();
  });
})();

});
