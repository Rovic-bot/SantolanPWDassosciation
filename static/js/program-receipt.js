/* Progressive receipt popup; the session-bound page remains the fallback. */
WorkspacePage.run(page => {
  'use strict';
  const {on, cleanup} = page;
  const dialog = document.querySelector('[data-program-receipt-dialog]');
  const body = dialog?.querySelector('[data-receipt-body]');
  const loading = dialog?.querySelector('[data-receipt-loading]');
  const recovery = dialog?.querySelector('[data-receipt-recovery]');
  const initial = document.querySelector('[data-program-receipt]');
  let receipt, receiptURL = location.href, opener, request, receiptEvents, printing = null;
  const canOpen = Boolean(dialog?.showModal);

  function enhance(item) {
    receiptEvents?.abort();
    receiptEvents = new AbortController();
    const listen = (target, type, listener) => target.addEventListener(type, listener, {signal:receiptEvents.signal});
    receipt = item;
    const reference = item.querySelector('#program-receipt-reference');
    const copy = item.querySelector('[data-receipt-copy]');
    copy.hidden = false;
    listen(copy, 'click', async () => {
      const status = item.querySelector('[data-receipt-copy-status]');
      try {
        if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(reference.textContent.trim());
        status.textContent = 'Reference copied.';
      } catch {
        reference.focus({preventScroll:true});
        const range = document.createRange(); range.selectNodeContents(reference);
        const selection = window.getSelection();
        selection.removeAllRanges(); selection.addRange(range);
        status.textContent = "Reference selected. Use your device's copy command.";
      }
    });
    const print = item.querySelector('[data-receipt-print]');
    print.hidden = false;
    listen(print, 'click', () => window.print());
    const buttons = [...item.querySelectorAll('[data-receipt-image]')];
    for (const button of buttons) {
      button.hidden = !window.ProgramReceiptImage;
      listen(button, 'click', async () => {
        const format = button.dataset.receiptImage, status = item.querySelector('[data-receipt-download-status]');
        buttons.forEach(control => {control.disabled = true;});
        status.textContent = `Preparing your ${format.toUpperCase()} receipt…`;
        try {
          const {blob, filename} = await window.ProgramReceiptImage(item, format);
          const url = URL.createObjectURL(blob), link = document.createElement('a');
          link.href = url; link.download = filename; link.hidden = true;
          item.append(link); link.click(); link.remove();
          page.setTimeout(() => URL.revokeObjectURL(url), 60000);
          cleanup(() => URL.revokeObjectURL(url));
          status.textContent = `${format.toUpperCase()} receipt ready. Check your downloads.`;
        } catch {
          status.textContent = 'The image could not be saved. Check that the receipt and QR code have loaded, then try again. You can also print your receipt.';
        } finally {buttons.forEach(control => {control.disabled = false;});}
      });
    }
    item.querySelector('[data-tracking-open]')?.setAttribute('aria-haspopup', 'dialog');
  }
  function focusReceipt() {
    dialog.scrollTop = 0;
    const heading = receipt?.querySelector('h1') || dialog.querySelector('[data-receipt-close]');
    heading.focus({preventScroll:true});
  }
  async function open(url, trigger) {
    if (!canOpen) return false;
    const destination = new URL(url, location.href);
    if (destination.origin !== location.origin) return false;
    receiptURL = destination.href;
    opener = trigger || document.activeElement;
    request?.abort();
    const pending = new AbortController(); request = pending;
    const timeout = window.setTimeout(() => pending.abort(), 15000);
    receiptEvents?.abort();
    body.replaceChildren(); receipt = null;
    loading.hidden = false; recovery.hidden = true;
    dialog.querySelector('[data-receipt-loading-status]').textContent = 'Loading your receipt…';
    dialog.querySelector('[data-receipt-full-page]').href = receiptURL;
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('receipt-is-open');
    try {
      const response = await fetch(destination, {credentials:'same-origin',cache:'no-store',signal:pending.signal});
      if (!response.ok || response.redirected || new URL(response.url).pathname !== destination.pathname) throw new Error('Receipt unavailable');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = parsed.querySelector('[data-program-receipt]');
      if (!content?.querySelector('#program-receipt-reference')) throw new Error('Receipt unavailable');
      content.querySelectorAll('script, noscript').forEach(node => node.remove());
      if (pending.signal.aborted || request !== pending) return true;
      body.replaceChildren(content); enhance(content);
      loading.hidden = true; focusReceipt();
    } catch {
      if (dialog.open && request === pending) {
        dialog.querySelector('[data-receipt-loading-status]').textContent = 'Your application was submitted, but the receipt could not be loaded. Try again or open the receipt page.';
        recovery.hidden = false;
      }
    } finally {window.clearTimeout(timeout);}
    return true;
  }
  const api = {open};
  window.ProgramReceipt = api;
  cleanup(() => {
    request?.abort();
    receiptEvents?.abort();
    document.body.classList.remove('receipt-is-open');
    if (window.ProgramReceipt === api) delete window.ProgramReceipt;
  });
  on(window, 'beforeprint', () => {
    const guidance = receipt?.querySelector('.program-receipt-guidance');
    if (guidance && !printing) {printing = {guidance, open:guidance.open}; guidance.open = true;}
  });
  on(window, 'afterprint', () => {
    if (printing) printing.guidance.open = printing.open;
    printing = null;
  });
  if (canOpen) {
    on(dialog.querySelector('[data-receipt-close]'), 'click', () => dialog.close());
    on(dialog.querySelector('[data-receipt-retry]'), 'click', () => open(receiptURL, opener));
    on(dialog, 'close', () => {
      request?.abort(); request = null;
      receiptEvents?.abort();
      body.replaceChildren(); receipt = null;
      document.body.classList.remove('receipt-is-open');
      opener?.focus({preventScroll:true});
    });
    on(dialog, 'keydown', event => {
      if (event.key !== 'Tab') return;
      const controls = [...dialog.querySelectorAll('a[href],button,summary,[tabindex]')].filter(el => {
        if (el.disabled || (el.tabIndex < 0 && el.tagName !== 'SUMMARY') || !el.getClientRects().length) return false;
        // Closed details can still report descendant rectangles in Chromium.
        // Only their summary is part of the keyboard sequence.
        const closed = el.closest('details:not([open])');
        return (!closed || el === closed.querySelector('summary')) && getComputedStyle(el).visibility !== 'hidden';
      });
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && (document.activeElement === first || document.activeElement.tabIndex < 0)) {event.preventDefault(); last?.focus();}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
    });
    const reopen = document.querySelector('[data-receipt-reopen]');
    if (reopen) on(reopen, 'click', () => open(receiptURL, reopen));
    if (initial) {
      document.querySelector('[data-receipt-return]').hidden = false;
      opener = reopen;
      body.append(initial); enhance(initial);
      dialog.showModal(); document.body.classList.add('receipt-is-open'); focusReceipt();
    }
  } else if (initial) enhance(initial);
});
