/* Private live conversation; native CSRF-protected forms remain the fallback. */
(() => {
  'use strict';
  const dates = new Intl.DateTimeFormat('en-PH', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Manila'});
  function initialize() {
    document.querySelectorAll('[data-referral-conversation]').forEach(root => {
      if (root.dataset.initialized) return;
      root.dataset.initialized = 'true';
      const log = root.querySelector('[data-conversation-messages]');
      const notice = root.querySelector('[data-conversation-notice]');
      const form = root.querySelector('[data-conversation-form]');
      const editor = form.elements.message;
      const button = form.querySelector('button[type=submit], button:not([type])');
      const known = new Set([...log.querySelectorAll('[data-message-id]')].map(node => node.dataset.messageId));
      let busy = false, sending = false, expired = false, uncertain = false, disconnected = false, controller;
      let version = Number(root.dataset.version);
      function resizeEditor() {
        if (!document.body.classList.contains('conversation-screen')) return;
        const nearEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
        editor.style.height = 'auto';
        editor.style.height = editor.value ? `${Math.min(editor.scrollHeight + 2, 104)}px` : '46px';
        if (nearEnd) log.scrollTop = log.scrollHeight;
      }
      editor.addEventListener('input', resizeEditor);
      resizeEditor();
      // Keep the composer above the mobile keyboard without scrolling the page.
      const viewport = window.visualViewport;
      function resizeViewport() {
        if (!root.isConnected) {
          viewport?.removeEventListener('resize', resizeViewport);
          viewport?.removeEventListener('scroll', resizeViewport);
          return;
        }
        if (!document.body.classList.contains('conversation-screen') || !viewport || viewport.scale !== 1) return;
        document.body.style.setProperty('--conversation-height', `${viewport.height}px`);
        document.body.style.setProperty('--conversation-top', `${viewport.offsetTop}px`);
      }
      viewport?.addEventListener('resize', resizeViewport);
      viewport?.addEventListener('scroll', resizeViewport);
      resizeViewport();
      log.scrollTop = log.scrollHeight;
      function clearHistory() {
        log.replaceChildren();
        root.querySelector('.concern-reference-details')?.remove();
        root.querySelector('.concern-conversation-heading')?.remove();
      }
      function finishConversation() {
        expired = true;
        const panel = document.createElement('section'), heading = document.createElement('h2'), text = document.createElement('p'), link = document.createElement('a');
        panel.className = 'resident-panel';
        panel.setAttribute('role', 'status');
        heading.textContent = 'This conversation has finished';
        text.textContent = 'The Association closed this concern. This conversation reference can no longer be used. Start a new concern to receive a new reference.';
        link.href = root.dataset.newConcernUrl; link.className = 'btn btn-primary'; link.textContent = 'Start a new concern';
        panel.append(heading, text, link);
        root.replaceChildren(panel);
        root.removeAttribute('data-ticket');
        root.removeAttribute('data-referral-conversation');
        root.dataset.conversationFinished = 'true';
        heading.tabIndex = -1; heading.focus();
      }
      function expire(message) {
        expired = true; clearHistory();
        notice.textContent = message;
        button.disabled = true;
      }
      async function read(response) {
        if (!root.isConnected) return null;
        if (response.status === 410) { finishConversation(); return null; }
        if (response.status === 409) {
          expire('Another conversation was opened in this browser. Save your draft and verify this conversation again.');
          return null;
        }
        if (response.status === 403) {
          expire('Your private session has ended. Save any draft, then reopen using your conversation reference.');
          return null;
        }
        if (![200, 400].includes(response.status) || response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('unavailable');
        return response.json();
      }
      function apply(data, {sent = false, recover = false, manual = false} = {}) {
        if (!data || !root.isConnected) return;
        if (data.closed) { finishConversation(); return; }
        if (data.ticket !== root.dataset.ticket) {
          expire('Another conversation was opened in this browser. Save your draft and verify this conversation again.');
          return;
        }
        if (data.version < version) return;
        version = data.version; root.dataset.version = version;
        const nearEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
        let added = 0;
        for (const item of data.messages) {
          if (known.has(String(item.id))) continue;
          const article = document.createElement('article');
          article.className = `concern-chat-message concern-chat-message--${item.sender === 'member' ? 'member' : 'staff'}`;
          article.dataset.messageId = item.id;
          const header = document.createElement('header'), name = document.createElement('strong'), time = document.createElement('time'), text = document.createElement('p');
          name.textContent = item.sender === 'member' ? 'You' : 'Association team';
          time.dateTime = item.recorded_at;
          time.textContent = dates.format(new Date(item.recorded_at));
          text.textContent = item.message;
          header.append(name, time); article.append(header, text); log.append(article);
          known.add(String(item.id)); added++;
        }
        if (sent || (added && nearEnd)) log.scrollTop = log.scrollHeight;
        root.querySelector('[data-conversation-status]').textContent = data.status;
        // A failed send retains its revision so a deliberate retry is idempotent.
        if ((!uncertain && !sending) || recover || sent) form.elements.version.value = version;
        if (added || manual) notice.textContent = added ? 'New messages received.' : 'You are up to date.';
      }
      async function update(manual = false) {
        if (busy || sending || expired || !root.isConnected || document.hidden || root.closest('[aria-busy=true]')) return;
        const dialog = root.closest('dialog');
        if (dialog && !dialog.open) return;
        busy = true; controller = new AbortController();
        try {
          const response = await fetch(root.dataset.updatesUrl, {credentials: 'same-origin', cache: 'no-store',
            headers: {'Accept': 'application/json'}, signal: controller.signal});
          const data = await read(response);
          if (data && disconnected && !uncertain) notice.textContent = 'Connected. Messages update automatically.';
          disconnected = false; apply(data, {manual});
        } catch (error) {
          if (error.name !== 'AbortError' && root.isConnected) {
            disconnected = true;
            notice.textContent = 'Connection interrupted. Reconnecting automatically; your draft is kept.';
          }
        } finally { busy = false; }
      }
      form.addEventListener('submit', async event => {
        event.preventDefault(); event.stopPropagation();
        if (sending || expired || !form.reportValidity()) return;
        const body = new FormData(form);
        const finish = window.ActionFeedback?.start(form, {button, label: 'Sending message…'});
        controller?.abort(); sending = true;
        button.disabled = true; editor.readOnly = true;
        form.setAttribute('aria-busy', 'true'); notice.textContent = 'Sending…';
        try {
          const data = await read(await fetch(form.action, {method: 'POST', body,
            credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}}));
          if (!data || !root.isConnected) return;
          uncertain = false; apply(data, {sent: data.sent, recover: true});
          if (expired) return;
          if (data.sent) { editor.value = ''; resizeEditor(); notice.textContent = 'Message sent.'; }
          else notice.textContent = data.errors?.join(' ') || 'Your message could not be sent. Your draft is kept.';
        } catch (error) {
          uncertain = true;
          if (root.isConnected) notice.textContent = 'Could not confirm sending. Your draft is kept. Check the conversation before trying Send again.';
        } finally {
          finish?.();
          sending = false; button.disabled = expired; editor.readOnly = false;
          form.removeAttribute('aria-busy');
          if (!uncertain && !expired) form.elements.version.value = version;
        }
      });
      root.querySelector('[data-conversation-refresh]')?.addEventListener('click', event => {
        event.preventDefault(); update(true);
      });
      async function tick() {
        if (!root.isConnected || expired) return;
        await update();
        if (root.isConnected && !expired) setTimeout(tick, 2000);
      }
      setTimeout(tick, 100);
      // Pause hidden conversations and check immediately when the member returns.
      const wake = () => {
        if (root.isConnected && !expired) update();
        else { document.removeEventListener('visibilitychange', wake); window.removeEventListener('online', wake); }
      };
      document.addEventListener('visibilitychange', wake);
      window.addEventListener('online', wake);
    });
  }
  initialize();
  document.addEventListener('public:concern-loaded', initialize);
})();
