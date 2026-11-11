WorkspacePage.run(({on, cleanup}) => {
  const dialogs = [...document.querySelectorAll('.membership-review-dialog')];
  if (!dialogs.length || !dialogs[0].showModal) return;
  let opener;
  const show = (dialog, source) => {
    opener = source;
    dialog.showModal();
    document.documentElement.classList.add('membership-dialog-open');
  };
  for (const dialog of dialogs) {
    dialog.querySelectorAll('[data-dialog-close]').forEach(button => on(button, 'click', () => dialog.close()));
    on(dialog, 'click', event => {
      if (event.target !== dialog) return;
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    });
    on(dialog, 'close', () => {
      document.documentElement.classList.remove('membership-dialog-open');
      opener?.focus({preventScroll: true});
    });
  }
  const pending = document.querySelector('#membership-pending-dialog');
  document.querySelectorAll('[data-pending-open]').forEach(button => on(button, 'click', () => {
    show(pending, button);
    pending.querySelector('textarea').focus();
  }));
  if (pending?.hasAttribute('data-open-on-load')) show(pending, document.querySelector('[data-pending-open]'));
  const form = pending?.querySelector('form');
  if (form) on(form, 'submit', () => {
    const send = form.querySelector('[type=submit]');
    send.disabled = true;
    send.textContent = 'Sending…';
  });
  const preview = document.querySelector('#membership-form-dialog');
  const frame = preview.querySelector('iframe');
  const print = preview.querySelector('[data-membership-preview-print]');
  const status = preview.querySelector('[data-membership-preview-status]');
  document.querySelectorAll('[data-membership-form-preview]').forEach(link => on(link, 'click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin) return;
    event.preventDefault();
    url.searchParams.set('preview', '1');
    print.disabled = true; status.textContent = 'Loading form preview…';
    show(preview, link); frame.src = url.href;
  }));
  on(frame, 'load', () => {
    if (!preview.open) return;
    const ready = Boolean(frame.contentDocument?.querySelector('.registration-content'));
    print.disabled = !ready;
    status.textContent = ready ? '' : 'The preview could not be loaded. Close it and reload the page to check your session.';
    if (ready) on(frame.contentDocument, 'keydown', event => {
      if (event.key === 'Escape' && preview.open) { event.preventDefault(); preview.close(); }
    });
  });
  on(print, 'click', () => { if (!print.disabled) { frame.contentWindow.focus(); frame.contentWindow.print(); } });
  on(preview, 'close', () => { frame.src = 'about:blank'; print.disabled = true; });
  cleanup(() => {
    dialogs.forEach(dialog => { if (dialog.open) dialog.close(); });
    document.documentElement.classList.remove('membership-dialog-open');
    frame.src = 'about:blank';
  });
  document.querySelector('[data-membership-preview-auto-open]')?.click();
});
