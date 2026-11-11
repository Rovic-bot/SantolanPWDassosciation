WorkspacePage.run(({on}) => {
  function selectRegistrationTab(root, selected, focus = false) {
    root.querySelectorAll('[data-registration-tab]').forEach(tab => {
      const active = tab === selected;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    root.querySelectorAll('[data-registration-panel]').forEach(panel => {
      panel.hidden = panel.dataset.registrationPanel !== selected.dataset.registrationTab;
    });
    if (focus) selected.focus({preventScroll: true});
  }
  function initializeRegistrationTabs(scope) {
    scope.querySelectorAll('[data-registration-tabs]').forEach(root => {
      if (root.hasAttribute('data-registration-enhanced')) return;
      const tabs = [...root.querySelectorAll('[data-registration-tab]')];
      if (!tabs.length) return;
      tabs.forEach(tab => {
        const panel = root.querySelector('#' + CSS.escape(tab.getAttribute('aria-controls')));
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', tab.id);
        panel.tabIndex = 0;
      });
      root.setAttribute('data-registration-enhanced', '');
      root.querySelector('[role=tablist]').hidden = false;
      selectRegistrationTab(root, tabs[0]);
    });
  }
  on(document, 'DOMContentLoaded', () => initializeRegistrationTabs(document));
  on(document, 'record-details:loaded', event => initializeRegistrationTabs(event.detail.root));
  on(document, 'click', event => {
    const tab = event.target.closest('[data-registration-tab]');
    if (!tab) return;
    selectRegistrationTab(tab.closest('[data-registration-tabs]'), tab);
  });
  on(document, 'keydown', event => {
    const tab = event.target.closest('[data-registration-tab]');
    if (!tab || event.altKey || event.ctrlKey || event.metaKey) return;
    const root = tab.closest('[data-registration-tabs]');
    const tabs = [...root.querySelectorAll('[data-registration-tab]')];
    let index = tabs.indexOf(tab);
    if (event.key === 'ArrowRight') index = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') index = (index + tabs.length - 1) % tabs.length;
    else if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = tabs.length - 1;
    else return;
    event.preventDefault();
    selectRegistrationTab(root, tabs[index], true);
  });

  // Keep section navigation inside the member popup; native links remain usable.
  on(document, 'click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('.member-record-nav a');
    if (!link) return;
    const root = link.closest('.member-record');
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !url.hash) return;
    const target = root?.querySelector('#' + CSS.escape(url.hash.slice(1)));
    if (!target) return;
    event.preventDefault();
    if (target.matches('details')) target.open = true;
    const scroller = root.closest('[data-record-dialog-content]');
    if (scroller) {
      // Scroll only the body so section links keep the dialog's close control visible.
      scroller.closest('dialog').scrollTop = 0;
      scroller.scrollTo({top: scroller.scrollTop + target.getBoundingClientRect().top
        - scroller.getBoundingClientRect().top - 16});
    } else {
      target.scrollIntoView({block: 'start'});
    }
    target.tabIndex = -1;
    target.focus({preventScroll: true});
  });
});
