WorkspacePage.run(page => {
  'use strict';
  const {on, cleanup} = page;
  const form = document.querySelector('[data-program-application]');
  if (!form || !window.fetch || !window.FormData) return;
  const summary = form.querySelector('[data-application-errors]');
  const list = summary.querySelector('ul');
  const verify = summary.querySelector('[data-application-reverify]');
  const button = form.querySelector('[type="submit"]');
  let saving = false, completed = false, controller;
  cleanup(() => controller?.abort());

  function showErrors(errors, reverify = false) {
    list.replaceChildren();
    for (const [name, messages] of Object.entries(errors)) {
      const field = form.elements.namedItem(name);
      for (const error of messages) {
        const item = document.createElement('li');
        if (field instanceof HTMLElement && field.id && field.type !== 'hidden') {
          field.setAttribute('aria-invalid', 'true');
          const link = document.createElement('a');
          const label = form.querySelector(`label[for="${CSS.escape(field.id)}"]`)?.textContent.trim() || name;
          link.href = `#${field.id}`;
          link.textContent = `${label}: ${error.message}`;
          link.addEventListener('click', event => { event.preventDefault(); field.focus(); });
          item.append(link);
        } else item.textContent = error.message;
        list.append(item);
      }
    }
    verify.hidden = !reverify;
    summary.hidden = false;
    summary.focus();
  }

  on(form, 'submit', async event => {
    event.preventDefault();
    if (saving || completed || !form.reportValidity()) return;
    summary.hidden = true;
    form.querySelectorAll('[aria-invalid]').forEach(field => field.removeAttribute('aria-invalid'));
    const data = new FormData(form); // The shared CSRF handler supplies the current token.
    const finish = window.ActionFeedback?.start(form, {button, label: 'Submitting application…'});
    saving = true;
    button.disabled = true;
    form.setAttribute('aria-busy', 'true');
    controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(form.action, {method:'POST', body:data, credentials:'same-origin',
        headers:{'Accept':'application/json', 'X-Program-Application':'1'}, signal:controller.signal});
      if (response.redirected && new URL(response.url).pathname === form.dataset.verifyUrl) {
        showErrors({__all__:[{message:'Membership verification expired or the record changed. Verify again in a new tab, then return here and submit.'}]}, true);
        return;
      }
      if (!response.headers.get('Content-Type')?.includes('application/json')) throw new Error('response');
      const result = await response.json();
      if (response.ok && result.redirect) {
        const destination = new URL(result.redirect, location.href);
        if (destination.origin !== location.origin || destination.pathname !== form.dataset.receiptUrl) throw new Error('destination');
        completed = true;
        const confirmation = document.createElement('section');
        confirmation.className = 'program-receipt-return';
        const message = document.createElement('p');
        message.textContent = 'Your application has been submitted. Save your receipt as an image or print a copy for your records.';
        const view = document.createElement('button');
        view.type = 'button'; view.className = 'btn btn-primary'; view.textContent = 'View receipt';
        view.dataset.receiptReopen = '';
        const showReceipt = async () => {
          if (!(await window.ProgramReceipt?.open(destination.href, view))) location.assign(destination.href);
        };
        on(view, 'click', showReceipt);
        const fallback = document.createElement('a');
        fallback.href = destination.href; fallback.textContent = 'Open receipt page';
        confirmation.append(message, view, fallback);
        form.replaceWith(confirmation);
        const heading = document.querySelector('.page-hero h1');
        if (heading) heading.textContent = 'Application submitted';
        const formHeading = confirmation.parentElement.querySelector('h2');
        if (formHeading) formHeading.textContent = 'Your receipt is ready';
        await showReceipt();
        return;
      }
      if ([422, 413].includes(response.status) && result.errors && Object.keys(result.errors).length) {
        showErrors(result.errors);
      } else throw new Error('response');
    } catch (_) {
      showErrors({__all__:[{message:'The submission could not be confirmed. Your entries and selected files are still here. Try submitting again.'}]});
    } finally {
      finish?.();
      window.clearTimeout(timeout);
      saving = false;
      button.disabled = completed;
      form.removeAttribute('aria-busy');
    }
  });
});
