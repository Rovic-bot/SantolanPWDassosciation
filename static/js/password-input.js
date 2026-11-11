WorkspacePage.run(({on}) => {
  document.querySelectorAll('[data-password-input]').forEach(wrapper => {
    const input = wrapper.querySelector('input');
    const toggle = wrapper.querySelector('[data-password-toggle]');
    if (!input || !toggle) return;
    const setVisible = visible => {
      input.type = visible ? 'text' : 'password';
      toggle.setAttribute('aria-label', `${visible ? 'Hide' : 'Show'} ${toggle.dataset.passwordLabel}`);
      toggle.querySelector('[data-password-slash]').toggleAttribute('hidden', !visible);
    };
    setVisible(false);
    toggle.hidden = false;
    on(toggle, 'click', () => setVisible(input.type === 'password'));
    if (input.form) {
      on(input.form, 'submit', () => setVisible(false));
      on(input.form, 'reset', () => setVisible(false));
    }
    on(window, 'pagehide', () => setVisible(false));
  });
});
