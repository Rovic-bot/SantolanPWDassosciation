// The external registry is reviewed by staff; no cross-site result is inferred.
window.SantolanPrpwd = {
  open(url, number, feedback) {
    if (!url || !number) return false;
    const show = message => { if (feedback) feedback.textContent = message; };
    let launched = false;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(number).then(
        () => { if (launched) show('PWD No. copied. Paste it into PRPWD and search, then return here to record the result.'); },
        () => { if (launched) show('Copy the PWD No. shown here and search it in PRPWD.'); });
    }
    const tab = window.open('about:blank', '_blank');
    if (!tab) { show('The browser blocked the new tab. Use Open PRPWD to try again.'); return false; }
    tab.opener = null;
    const policy = tab.document.createElement('meta');
    policy.name = 'referrer'; policy.content = 'no-referrer'; tab.document.head.append(policy);
    tab.location.replace(url);
    launched = true;
    show('PRPWD opened. Check the PWD No. there, then return here to record the result.');
    return true;
  }
};

WorkspacePage.run(({on}) => {
  document.querySelectorAll('[data-prpwd-review]').forEach(panel => {
    const form = panel.dataset.reviewForm ? document.getElementById(panel.dataset.reviewForm) : panel.closest('form');
    if (!form) return;
    const number = form.elements.namedItem('pwd_number');
    const opened = form.elements.namedItem('prpwd_lookup_number');
    if (!number || !opened) return;
    const feedback = panel.querySelector('[data-prpwd-feedback]');
    const buttons = Array.from(form.elements).filter(element => element.matches('[data-prpwd-decision]'));
    const onlineFlow = panel.closest('[data-online-review-flow]');
    const approvalControls = onlineFlow?.querySelector('.association-approval-controls');
    const invitation = onlineFlow?.querySelector('#office-invitation-form');
    const invitationButton = invitation?.querySelector('[data-prpwd-invitation]');
    const attestation = invitation?.elements.namedItem('prpwd_verified');
    const refresh = () => {
      const ready = Boolean(number.value && opened.value === number.value && panel.dataset.prpwdUrl);
      if (approvalControls) approvalControls.disabled = !ready;
      if (invitationButton) {
        const saved = number.value === panel.dataset.savedPwd;
        invitation.elements.namedItem('prpwd_lookup_number').value = ready && saved ? number.value : '';
        invitationButton.disabled = !ready || !saved || !attestation.checked;
        if (!saved) feedback.textContent = 'Save the PWD number correction first, then check that saved number in PRPWD before sending the invitation.';
      }
      const officeConfirmation = form.elements.namedItem('office_verification_confirmed');
      if (onlineFlow && officeConfirmation) {
        officeConfirmation.disabled = !ready;
      }
      if (!ready && officeConfirmation) {
        officeConfirmation.checked = false;
      }
      buttons.forEach(button => {
        button.disabled = !ready || (button.value === 'approve_registration' &&
          (officeConfirmation && !officeConfirmation.checked));
      });
      if (!ready) feedback.textContent = panel.dataset.reviewForm ? 'Check PRPWD before confirming.' : 'Open PRPWD and check this PWD No. before recording a decision.';
    };
    on(panel.querySelector('[data-prpwd-open]'), 'click', () => {
      if (!number.value || !number.checkValidity()) { number.reportValidity(); number.focus(); return; }
      if (window.SantolanPrpwd.open(panel.dataset.prpwdUrl, number.value, feedback)) {
        opened.value = number.value; refresh();
      }
    });
    on(number, 'input', () => { opened.value = ''; if (attestation) attestation.checked = false; refresh(); });
    if (attestation) on(attestation, 'change', refresh);
    const officeConfirmation = form.elements.namedItem('office_verification_confirmed');
    if (officeConfirmation) on(officeConfirmation, 'change', refresh);
    on(form, 'submit', event => {
      if (onlineFlow && event.submitter?.value === 'approve_registration' &&
          (!number.value || opened.value !== number.value || !officeConfirmation?.checked)) {
        event.preventDefault();
        refresh();
        onlineFlow.querySelector('#office-approval-help')?.focus();
      }
    });
    refresh();
  });
});
