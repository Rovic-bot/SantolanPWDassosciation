/* Local translations of interface labels only; never change stored records or input values. */
WorkspacePage.run(({on, cleanup, MutationObserver}) => {
  if (!document.body.classList.contains('admin-workspace')) return;
  const labels = {
    'Make yourself comfortable.': 'Gawing komportable ang iyong paggamit.',
    'Adjust how this website looks on this device.': 'Ayusin ang hitsura ng website sa device na ito.',
    'Display': 'Display', 'Display preferences': 'Mga kagustuhan sa display',
    'Close display preferences': 'Isara ang mga kagustuhan sa display',
    'Text size': 'Laki ng teksto', 'Standard': 'Karaniwan', 'Larger': 'Mas malaki', 'Largest': 'Pinakamalaki',
    'Dark mode': 'Madilim na mode', 'High contrast': 'Mataas na contrast', 'Reduce motion': 'Bawasan ang paggalaw',
    'Your device’s reduced motion setting is always respected.': 'Palaging sinusunod ang setting ng device para sa bawas na paggalaw.',
    'Reset preferences': 'Ibalik ang mga default',
    'Highlight text on the page, then choose Read aloud. Keyboard shortcut: Alt + R.': 'Piliin ang teksto sa pahina, saka piliin ang Basahin nang malakas. Shortcut: Alt + R.',
    'Read aloud': 'Basahin nang malakas', 'Close read aloud': 'Isara ang pagbasa',
    'Display preferences updated.': 'Na-update ang mga kagustuhan sa display.',
    'Display preferences reset.': 'Naibalik ang mga default na kagustuhan.',
    'Dashboard': 'Dashboard', 'Overview': 'Pangkalahatang-ideya', 'Members': 'Mga miyembro',
    'Member directory': 'Talaan ng mga miyembro', 'Directory': 'Talaan', 'Membership Reviews': 'Pagsusuri ng membership',
    'Membership reviews': 'Pagsusuri ng membership', 'Membership': 'Membership',
    'Programs & Events': 'Mga programa at kaganapan', 'Programs': 'Mga programa', 'Events': 'Mga kaganapan',
    'Announcements': 'Mga anunsiyo', 'Reports': 'Mga ulat', 'Administration': 'Administrasyon',
    'Settings': 'Mga setting', 'Applications': 'Mga aplikasyon', 'Assistance': 'Tulong',
    'Community Assistance': 'Tulong sa komunidad', 'Program ranking': 'Pagraranggo sa programa',
    'Change password': 'Palitan ang password', 'Sign out': 'Mag-sign out', 'SIGNED IN AS': 'NAKA-SIGN IN BILANG',
    'View Public Site': 'Tingnan ang pampublikong website', 'Menu': 'Menu', 'Workspace': 'Workspace'
  };
  const selector = '[data-display-widget], [data-selection-reader], [data-selection-status], [data-module-label], .workspace-module-links a, .workspace-account .account-label, .workspace-account a, .workspace-account button, .dashboard-public-link';
  const originals = new WeakMap();
  const normalize = value => value.replace(/\s+/g, ' ').trim();
  let scheduled = false;
  function apply() {
    scheduled = false;
    observer.disconnect();
    const active = document.documentElement.dataset.language === 'tl';
    document.documentElement.lang = active ? 'tl' : 'en';
    document.querySelectorAll(selector).forEach(element => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (node.parentElement.closest('script,style,svg,input,textarea,[translate="no"],[data-public-language]')) continue;
        const previous = originals.get(node);
        const source = previous && previous.output === node.nodeValue ? previous.source : node.nodeValue;
        const translated = active ? labels[normalize(source)] : null;
        const output = translated ? source.replace(source.trim(), translated) : source;
        if (node.nodeValue !== output) node.nodeValue = output;
        originals.set(node, {source, output});
      }
    });
    const language = document.querySelector('[data-public-language]');
    for (const [selector, label] of [['.display-trigger', 'Display preferences'], ['.display-close', 'Close display preferences']]) {
      document.querySelector(selector)?.setAttribute('aria-label', active ? labels[label] : label);
    }
    if (language) {
      language.textContent = active ? 'English' : 'Tagalog';
      language.setAttribute('aria-label', active ? 'Bumalik sa English' : 'Translate interface labels to Tagalog');
    }
    observer.observe(document.body, {subtree: true, childList: true, characterData: true});
  }
  const observer = new MutationObserver(() => {
    if (!scheduled) { scheduled = true; queueMicrotask(apply); }
  });
  on(document, 'santolan:displaychange', apply);
  cleanup(() => observer.disconnect());
  apply();
});
