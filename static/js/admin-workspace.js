/* Add keyboard access and accessible names around Django's existing widgets. */
(() => {
  'use strict';
  document.querySelectorAll('#changelist .results').forEach(region => {
    region.tabIndex = 0;
    region.setAttribute('role', 'region');
    const heading = document.querySelector('#content h1');
    region.setAttribute('aria-label', (heading?.textContent.trim() || 'Administration') + ' records');
  });

  // Split date/time widgets have visible text but no labels linked to their inputs.
  document.querySelectorAll('.datetime').forEach(widget => {
    const label = widget.previousElementSibling;
    const fieldName = label?.tagName === 'LABEL' ? label.textContent.trim().replace(/:$/, '') : '';
    widget.querySelectorAll('input.vDateField, input.vTimeField').forEach(input => {
      if (input.labels.length || input.hasAttribute('aria-label') || input.hasAttribute('aria-labelledby')) return;
      const partName = input.previousSibling?.textContent.trim().replace(/:$/, '');
      if (partName) input.setAttribute('aria-label', [fieldName, partName].filter(Boolean).join(' — '));
    });
  });
})();
