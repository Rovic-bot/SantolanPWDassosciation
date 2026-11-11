WorkspacePage.run(({on}) => {
  const frame = document.querySelector('[data-pdao-receipt-frame]');
  const link = document.querySelector('[data-pdao-receipt-print]');
  if (!frame || !link) return;
  on(link, 'click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (!frame.contentDocument?.querySelector('.pdao-sheet')) return;
    event.preventDefault();
    frame.contentWindow.focus();
    frame.contentWindow.print();
  });
});
