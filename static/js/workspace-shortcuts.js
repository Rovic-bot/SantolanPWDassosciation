/* Double-click shortcuts open existing authorized views; never submit an action. */
'use strict';
WorkspacePage.run(({on}) => {
  const selectors = [
    '[data-ewaf-selection] [data-program-row]',
    '[data-release-portfolio] [data-release-row]',
    '[data-announcement-programs] [data-announcement-row]',
    '[data-application-workspace] [data-program-card]',
    '[data-referral-inbox] tr[data-ticket-id]',
    '[data-event-workspace] .event-agenda-card[data-event-id]'
  ].join(',');
  const selectionLinks = '[data-select-program], [data-release-select], [data-announcement-select]';
  on(document, 'dblclick', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const row = event.target.closest(selectors);
    if (!row || row.closest('[hidden], [inert]')) return;
    const control = event.target.closest('a, button, input, select, textarea, summary, label, [contenteditable]');
    // Explicit links/buttons keep their normal single-click behavior.
    if (control && !control.matches(selectionLinks)) return;
    let link;
    if (row.dataset.rankingUrl) {
      const url = new URL(row.dataset.rankingUrl, location.href);
      if (url.origin === location.origin) { event.preventDefault(); location.assign(url.href); }
      return;
    }
    if (row.hasAttribute('data-release-row') || row.hasAttribute('data-announcement-row')) {
      if (row.dataset.selected !== 'true') row.querySelector(selectionLinks)?.click();
      const release = row.hasAttribute('data-release-row');
      const id = release ? row.dataset.releaseRow : row.dataset.announcementRow;
      const panel = document.querySelector(`[data-${release ? 'release' : 'announcement'}-panel="${CSS.escape(id)}"]`);
      link = panel?.querySelector(release ? 'a[data-release-dialog]' : 'a[data-results-preview]');
    } else if (row.hasAttribute('data-program-card')) link = row.querySelector('a[data-review-program]');
    else if (row.hasAttribute('data-ticket-id')) link = row.querySelector('a.referral-view-ticket');
    else if (row.hasAttribute('data-event-id')) link = row.querySelector('a[data-event-dialog]');
    if (!link || link.matches('[aria-disabled="true"]') || new URL(link.href).origin !== location.origin) return;
    event.preventDefault(); link.click();
  });
});
