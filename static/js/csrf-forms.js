/* A sign-in in another tab rotates Django's CSRF cookie. Keep open forms current. */
(() => {
  'use strict';
  const cookieName = document.currentScript?.dataset.csrfCookie;
  if (!cookieName) return;

  function synchronize(form, data) {
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== 'post') return;
    if (new URL(form.action, location.href).origin !== location.origin) return;
    const fields = form.querySelectorAll('input[name="csrfmiddlewaretoken"]');
    if (!fields.length) return;
    const prefix = `${cookieName}=`;
    const cookie = document.cookie.split(';').map(item => item.trim()).find(item => item.startsWith(prefix));
    const token = cookie?.slice(prefix.length);
    // Django accepts the current unmasked cookie secret. Leave server-rendered
    // tokens alone when cookies are unavailable (e.g. HttpOnly/session CSRF).
    if (!token || !/^[a-zA-Z0-9]{32}$/.test(token)) return;
    fields.forEach(field => { field.value = token; });
    if (data) data.set('csrfmiddlewaretoken', token);
  }

  document.addEventListener('submit', event => synchronize(event.target), true);
  document.addEventListener('formdata', event => synchronize(event.target, event.formData), true);
  const refresh = () => document.querySelectorAll('form').forEach(form => synchronize(form));
  window.addEventListener('pageshow', refresh);
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
