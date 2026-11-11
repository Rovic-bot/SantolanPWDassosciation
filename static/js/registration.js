WorkspacePage.run(({on}) => {
document.querySelectorAll('[data-registration-number]').forEach(input => {
  const allowed = input.dataset.registrationNumber === 'hyphens' ? /^[0-9-]*$/ : /^[0-9]*$/;
  let previous = input.value;
  const restoreInvalidInput = () => {
    if (allowed.test(input.value)) {
      previous = input.value;
    } else {
      const caret = input.selectionStart;
      input.value = previous;
      if (caret !== null) input.setSelectionRange(Math.min(caret, previous.length), Math.min(caret, previous.length));
    }
  };
  input.addEventListener('keydown', event => {
    if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.length === 1 && !allowed.test(event.key)) {
      event.preventDefault();
    }
  });
  input.addEventListener('beforeinput', event => {
    if (event.data && !allowed.test(event.data)) event.preventDefault();
  });
  input.addEventListener('paste', event => {
    const text = event.clipboardData?.getData('text');
    // Reject an invalid paste as a whole; never silently change an ID number.
    if (text && !allowed.test(text)) event.preventDefault();
  });
  input.addEventListener('input', event => { if (!event.isComposing) restoreInvalidInput(); });
  input.addEventListener('change', restoreInvalidInput);
  input.addEventListener('compositionend', restoreInvalidInput);
});

document.querySelectorAll('[data-registration-print]').forEach(button => {
  button.addEventListener('click', () => window.print());
});

document.querySelectorAll('[data-income-step]').forEach(input => {
  const adjust = direction => {
    if (input.disabled || input.readOnly) return;
    const value = input.value === '' ? Number(input.dataset.incomeStart)
      : Math.max(0, Number(input.value) + direction * Number(input.dataset.incomeStep));
    if (!Number.isFinite(value)) return;
    input.value = String(Math.round(value * 100) / 100);
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
  };
  on(input, 'wheel', event => {
    if (document.activeElement !== input || !event.deltaY || event.ctrlKey || input.disabled || input.readOnly) return;
    event.preventDefault();
    adjust(event.deltaY < 0 ? 1 : -1);
  }, {passive: false});
  on(input, 'keydown', event => {
    if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    adjust(event.key === 'ArrowUp' ? 1 : -1);
  });
});

document.querySelectorAll('[data-registration-print-reference]').forEach(button => {
  button.hidden = false;
  button.addEventListener('click', () => {
    document.body.classList.add('registration-reference-print');
    try {
      window.print();
    } finally {
      document.body.classList.remove('registration-reference-print');
    }
  });
});

document.querySelectorAll('[data-registration-copy]').forEach(button => {
  const reference = document.getElementById(button.dataset.registrationCopy);
  const feedback = document.getElementById('reference-copy-feedback');
  if (!reference || !feedback) return;
  button.hidden = false;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(reference.textContent.trim());
      feedback.textContent = 'Reference number copied. Keep it for your barangay visit.';
      button.querySelector('[data-copy-label]').textContent = 'Copied!';
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(reference);
      selection?.removeAllRanges();
      selection?.addRange(range);
      feedback.textContent = 'Select and copy the reference number above, or take a screenshot.';
    } finally {
      button.disabled = false;
    }
  });
});

document.querySelectorAll('[data-registration-view]').forEach(link => {
  link.addEventListener('click', () => {
    const form = document.getElementById('submitted-form');
    if (!form) return;
    form.querySelectorAll('[data-registration-section]').forEach(section => { section.open = true; });
    form.focus({preventScroll: true});
  });
});

// Include all retained sections when printing older form formats, then restore
// the user's expanded/collapsed sections when the print dialog closes.
let registrationPrintSections = null;
on(window, 'beforeprint', () => {
  if (registrationPrintSections) return;
  registrationPrintSections = [...document.querySelectorAll('[data-registration-section]')]
    .map(section => [section, section.open]);
  registrationPrintSections.forEach(([section]) => { section.open = true; });
});
on(window, 'afterprint', () => {
  registrationPrintSections?.forEach(([section, open]) => { section.open = open; });
  registrationPrintSections = null;
});

document.querySelectorAll('[data-registration-age]').forEach(output => {
  const input = document.getElementById(output.getAttribute('for'));
  if (!input) return;
  const update = () => {
    const born = new Date(`${input.value}T00:00:00`);
    const today = input.max ? new Date(`${input.max}T00:00:00`) : new Date();
    if (Number.isNaN(born.getTime()) || born > today) {
      output.textContent = 'Calculated from date of birth';
      return;
    }
    const beforeBirthday = today.getMonth() < born.getMonth() ||
      (today.getMonth() === born.getMonth() && today.getDate() < born.getDate());
    output.textContent = `${today.getFullYear() - born.getFullYear() - Number(beforeBirthday)} years`;
  };
  input.addEventListener('change', update);
  update();
});

});
