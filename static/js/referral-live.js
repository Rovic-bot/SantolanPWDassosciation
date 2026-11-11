/* Update private staff conversations in place; never retry a write automatically. */
'use strict';
WorkspacePage.run(({on, fetch, setTimeout}) => {
  const dates = new Intl.DateTimeFormat('en-PH', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Manila'});
  const parse = html => new DOMParser().parseFromString(html, 'text/html').body.firstElementChild;
  function active(root) {
    return root.isConnected && !document.hidden && (!root.closest('dialog') || root.closest('dialog').open);
  }
  async function json(url, options = {}) {
    const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', ...options,
      headers: {'Accept': 'application/json'}});
    if ([401, 403].includes(response.status) || response.redirected) throw new Error('access');
    if (![200, 400].includes(response.status) || !response.headers.get('content-type')?.includes('application/json')) throw new Error('unavailable');
    return response.json();
  }
  function initialize(root) {
    const ticket = root.matches?.('[data-referral-ticket]') ? root : root.querySelector('[data-referral-ticket]');
    if (!ticket || ticket.dataset.liveInitialized) return;
    ticket.dataset.liveInitialized = 'true';
    const log = ticket.querySelector('.referral-conversation');
    const form = ticket.querySelector('[data-referral-reply]');
    const notice = ticket.querySelector('[data-referral-live-notice]');
    const editor = form?.elements.namedItem('member_message');
    const channel = form?.elements.namedItem('channel');
    const button = form?.querySelector('[data-reply-submit]');
    const avatar = ticket.querySelector('.referral-message--member .referral-message-avatar');
    const known = new Set([...log.querySelectorAll('[data-message-id]')].map(node => node.dataset.messageId));
    let polling = false, sending = false, uncertain = false, stopped = false, disconnected = false, controller, emailRevision;
    let version = Number(ticket.dataset.version);
    log.setAttribute('role', 'log');
    log.setAttribute('aria-relevant', 'additions');
    log.scrollTop = log.scrollHeight;
    function say(text, error = false) {
      if (notice) { notice.textContent = text; notice.dataset.error = String(error); }
    }
    if (channel) {
      try {
        const saved = localStorage.getItem(ticket.dataset.channelKey);
        if ([...channel.options].some(option => option.value === saved)) channel.value = saved;
      } catch (_) { /* Storage can be disabled; the current form still retains its choice. */ }
      channel.dispatchEvent(new Event('change'));
      channel.addEventListener('change', () => {
        try { localStorage.setItem(ticket.dataset.channelKey, channel.value); } catch (_) {}
      });
    }
    function refreshPanel(selector, html) {
      const current = ticket.querySelector(selector);
      if (!current || current.contains(document.activeElement)) return false;
      if ([...current.querySelectorAll('textarea')].some(input => input.value)) return false;
      const next = parse(html);
      if (!next || current.outerHTML === next.outerHTML) return true;
      const details = [current, ...current.querySelectorAll('details')].map(node => node.open);
      [next, ...next.querySelectorAll('details')].forEach((node, index) => {
        if (node.tagName === 'DETAILS') node.open = !!details[index];
      });
      current.replaceWith(next);
      return true;
    }
    function apply(data, {sent = false, recover = false} = {}) {
      if (!ticket.isConnected || data.ticket !== ticket.dataset.referralTicket || data.version < version) return;
      version = data.version;
      ticket.dataset.version = version;
      const nearEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 65;
      let added = 0;
      for (const item of data.messages) {
        if (known.has(String(item.id))) continue;
        const member = item.sender === 'member';
        const article = document.createElement('article');
        article.className = `referral-message referral-message--${member ? 'member' : 'staff'}`;
        article.dataset.messageId = item.id;
        article.setAttribute('aria-label', member ? `Message from ${ticket.dataset.memberName}` : 'Association reply');
        if (member && avatar) {
          const photo = avatar.cloneNode(true);
          photo.querySelector('img')?.addEventListener('error', event => { event.target.hidden = true; }, {once: true});
          article.append(photo);
        }
        const content = document.createElement('div'), bubble = document.createElement('div'), time = document.createElement('time');
        content.className = 'referral-message-content';
        bubble.className = 'referral-message-bubble referral-message-bubble--live';
        bubble.textContent = item.message;
        time.className = 'referral-message-time'; time.dateTime = item.recorded_at;
        time.textContent = dates.format(new Date(item.recorded_at));
        content.append(bubble, time); article.append(content); log.append(article);
        known.add(String(item.id)); added++;
      }
      if (sent || (added && nearEnd)) log.scrollTop = log.scrollHeight;
      const status = ticket.querySelector('.referral-ticket-header .referral-status');
      if (status) {
        const dot = document.createElement('span'); dot.setAttribute('aria-hidden', 'true');
        status.replaceChildren(dot, document.createTextNode(data.status));
        status.className = `referral-status referral-status--${data.status_code}`;
      }
      ticket.querySelectorAll('input[name=version]').forEach(input => {
        if (input.form !== form || (!uncertain && !sending) || recover || sent) input.value = version;
      });
      if (form && (!uncertain || recover || sent)) form.elements.sender_version.value = data.sender_version;
      const sender = ticket.querySelector('[data-referral-sender]');
      if (sender) sender.textContent = data.sender_email || 'Not configured';
      refreshPanel('[data-referral-activity]', data.activity_html);
      if (emailRevision !== data.email_revision && refreshPanel('.referral-email-history', data.email_html)) emailRevision = data.email_revision;
      if (added && !sent) say('New messages received.');
      if (form && (data.closed || !data.can_review)) {
        stopped = true;
        form.querySelectorAll('button, input, select, textarea').forEach(control => { control.disabled = true; });
        ticket.querySelectorAll('.referral-ticket-actions button').forEach(control => { control.disabled = true; });
        say(data.closed ? 'This conversation is closed.' : 'You now have view-only access to this conversation.');
      }
      if (data.closed) stopped = true;
    }
    async function poll() {
      if (polling || sending || stopped || !active(ticket)) return;
      polling = true; controller = new AbortController();
      try {
        const data = await json(ticket.dataset.updatesUrl, {signal: controller.signal});
        if (disconnected && !uncertain) say('Connected. Messages update automatically.');
        disconnected = false; apply(data);
      }
      catch (error) {
        if (error.name === 'AbortError' || !ticket.isConnected) return;
        if (error.message === 'access') {
          stopped = true; if (button) button.disabled = true;
          say('Your access has ended. Save your draft, then sign in again.', true);
        } else { disconnected = true; say('Connection interrupted. Reconnecting automatically; your draft is kept.', true); }
      } finally { polling = false; }
    }
    form?.addEventListener('submit', async event => {
      event.preventDefault(); event.stopPropagation();
      if (sending || stopped || !form.reportValidity()) return;
      const body = new FormData(form);
      const finish = window.ActionFeedback?.start(form, {button,
        label: channel.value === 'email' ? 'Sending email…' : 'Sending message…'});
      controller?.abort(); sending = true;
      button.disabled = true; channel.disabled = true; editor.readOnly = true;
      form.setAttribute('aria-busy', 'true'); say('Sending…');
      try {
        const data = await json(form.action, {method: 'POST', body});
        if (!ticket.isConnected) return;
        uncertain = false;
        apply(data, {sent: data.sent, recover: true});
        if (data.sent) { editor.value = ''; say(data.notice, data.delivery_error); }
        else say(data.errors?.join(' ') || 'Your message could not be sent. Your draft is kept.', true);
      } catch (error) {
        uncertain = true;
        if (error.message === 'access') stopped = true;
        say(error.message === 'access' ? 'Your access has ended. Save your draft, then sign in again.' :
          'Could not confirm sending. Your draft is kept. Check the conversation before trying Send again.', true);
      } finally {
        finish?.();
        sending = false; button.disabled = stopped; channel.disabled = stopped; editor.readOnly = stopped;
        form.removeAttribute('aria-busy');
        if (!uncertain && !stopped) form.elements.version.value = version;
      }
    });
    async function tick() {
      if (!ticket.isConnected || stopped) return;
      await poll();
      if (!stopped && ticket.isConnected) setTimeout(tick, 2000);
    }
    on(window, 'online', poll);
    on(document, 'visibilitychange', () => { if (!document.hidden) poll(); });
    setTimeout(tick, 100);
  }
  initialize(document);
  on(document, 'record-details:loaded', event => initialize(event.detail.root));

  const inbox = document.querySelector('[data-referral-inbox]');
  if (inbox) {
    let busy = false, stopped = false;
    async function updateInbox() {
      if (!active(inbox) || busy || stopped) return;
      busy = true;
      try {
        const url = new URL(inbox.dataset.inboxUrl, location.href); url.search = location.search;
        const data = await json(url);
        if (!inbox.isConnected) return;
        inbox.querySelectorAll('[data-referral-total]').forEach(node => { node.textContent = data.totals[node.dataset.referralTotal]; });
        const current = inbox.querySelector('.referral-results'), next = parse(data.results_html);
        if (next && !current.contains(document.activeElement) && current.outerHTML !== next.outerHTML) {
          const horizontal = current.querySelector('.table-responsive').scrollLeft;
          current.replaceWith(next);
          next.querySelector('.table-responsive').scrollLeft = horizontal;
        }
      } catch (error) { if (error.message === 'access') stopped = true; }
      finally { busy = false; }
    }
    async function tick() {
      if (!inbox.isConnected || stopped) return;
      await updateInbox();
      if (!stopped && inbox.isConnected) setTimeout(tick, 3000);
    }
    on(window, 'online', updateInbox);
    on(document, 'visibilitychange', () => { if (!document.hidden) updateInbox(); });
    on(document, 'record-details:closed', updateInbox);
    setTimeout(tick, 3000);
  }
});
