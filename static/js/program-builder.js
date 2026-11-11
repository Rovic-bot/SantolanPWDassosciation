WorkspacePage.run(({on, addEventListener, fetch, requestAnimationFrame}) => {
/* Progressive enhancement of the existing protected Django program form. */
(() => {
  'use strict';
  if (!document.querySelector('[data-program-builder]') || !window.fetch) return;
  let active;

  /** @param {HTMLElement} root */
  function setup(root) {
    const form = root.querySelector('[data-builder-form]'), status = root.querySelector('[data-draft-status]');
    const ranges = new Map(), saveFeedback = root.querySelector('[data-save-feedback]');
    let saving = false, uncertain = false, initial = '', reviewed = false;
    const value = name => form.elements.namedItem(name)?.value?.trim() || '';
    const serial = () => JSON.stringify([...new FormData(form)].filter(([name]) => name !== 'csrfmiddlewaretoken')
      .map(([name, entry]) => [name, entry instanceof File ? (entry.name ? [entry.name, entry.size, entry.lastModified] : null) : entry]));
    const dirty = () => serial() !== initial || [...ranges.values()].some(range => range.pending());
    const validFields = section => [...root.querySelectorAll(`${section} input[name], ${section} select[name], ${section} textarea[name]`)].every(input => input.name === 'notes' || input.checkValidity());
    const readiness = (name, complete, label) => {
      const item = root.querySelector(`[data-readiness="${name}"]`); item.dataset.complete = String(complete);
      item.firstElementChild.textContent = complete ? '✓' : '○'; item.querySelector('[data-ready-label]').textContent = label;
    };
    function update() {
      root.querySelector('[data-preview-title]').textContent = value('name') || 'Untitled program';
      const category = form.elements.namedItem('assistance_type');
      root.querySelector('[data-preview-category]').textContent = category.selectedOptions[0]?.textContent || 'Choose assistance type';
      const slots = form.elements.namedItem('slots');
      slots.required = true;
      root.querySelector('[data-preview-capacity]').textContent = value('slots') ? `${value('slots')} places` : 'Not set';
      root.querySelector('[data-preview-selection]').textContent = 'EWAF required';
      const details = !!value('name') && !!value('assistance_type') && validFields('#setup-identity');
      const capacity = validFields('#setup-capacity') && Number(value('slots')) > 0;
      const requirements = validFields('#setup-requirements');
      readiness('details', details, details ? 'Details complete' : 'Required details missing');
      readiness('capacity', capacity, capacity ? 'Capacity configured' : 'Beneficiary slots required for EWAF');
      for (const [name, range] of ranges) readiness(name, range.complete(), range.complete() ? 'Dates and times set' : range.pending() ? 'Complete dates and times' : name === 'delivery' ? 'Not set · optional' : 'Dates required');
      const count = form.querySelectorAll('[name=eligible_disability_types]:checked').length;
      readiness('eligibility', count > 0 || Number(root.dataset.retainedTypes) > 0, count ? `${count} selected` : Number(root.dataset.retainedTypes) > 0 ? 'Earlier classifications retained' : 'Select at least one disability type');
      readiness('requirements', requirements, requirements ? 'Requirements checked' : 'Required information missing');
      const ready = root.querySelectorAll('[data-readiness][data-complete=true]').length;
      root.querySelector('[data-ready-count]').textContent = `${ready} of 6 setup areas complete`;
      const changed = dirty();
      status.textContent = changed || root.dataset.persisted !== 'true' ? 'Unsaved changes' : root.dataset.savedLabel;
      status.dataset.state = changed || root.dataset.persisted !== 'true' ? 'unsaved' : 'saved';
      if (changed && reviewed) { root.querySelector('[data-review-ready]').hidden = true; reviewed = false; }
      if (root.querySelector('[data-validation-summary]').dataset.client === 'true' && validation(false)) saveFeedback.textContent = 'Changes ready to save.';
    }
    function renumberQuestions() {
      const rows = [...root.querySelectorAll('[data-question-rows] [data-question]')];
      rows.forEach((row, index) => {
        row.querySelector('[data-question-number]').textContent = String(index + 1);
        for (const node of row.querySelectorAll('[name], [id], [for], [aria-describedby]')) {
          for (const attribute of ['name','id','for','aria-describedby']) if (node.hasAttribute(attribute)) node.setAttribute(attribute, node.getAttribute(attribute).replace(/requirements-(?:\d+|__prefix__)-/g, `requirements-${index}-`));
        }
        row.querySelector('[name$="-label"]').required = true;
        row.querySelector('[data-remove-question]').setAttribute('aria-label', `Remove requirement ${index + 1}`);
      });
      const total = form.elements.namedItem('requirements-TOTAL_FORMS');
      if (total) total.value = String(rows.length);
      const add = root.querySelector('[data-add-question]');
      if (add) add.disabled = rows.length >= 50;
    }
    function validation(focus = true) {
      const errors = [], targetFor = input => root.querySelector(`label[for="${CSS.escape(input.id)}"]`)?.textContent.trim().replace(/\s*\*$/, '') || input.name;
      for (const input of form.querySelectorAll('input[name], select[name], textarea[name]')) {
        if (input.closest('[data-native-dates]')) continue;
        if (!input.checkValidity()) { errors.push({text: `${targetFor(input)}: ${input.validationMessage}`, target: input}); input.setAttribute('aria-invalid', 'true'); }
      }
      if (!form.querySelector('[name=eligible_disability_types]:checked') && !Number(root.dataset.retainedTypes)) {
        errors.push({text: 'Select at least one disability type, or choose Select all.', target: root.querySelector('[data-disability-selection]')});
      }
      for (const [name, range] of ranges) {
        if (range.error()) errors.push({text: `${name === 'registration' ? 'Registration window' : 'Program schedule'}: ${range.error()}`, range, target: root.querySelector(`[data-range=${name}]`)});
      }
      if (value('ends_at') && value('registration_closes_at') > value('ends_at')) errors.push({text: 'Close registration no later than the program end.', range: ranges.get('registration'), target: root.querySelector('[data-range=registration]')});
      const box = root.querySelector('[data-validation-summary]'), content = box.querySelector('[data-validation-content]');
      box.dataset.client = 'true';
      box.hidden = !errors.length;
      if (errors.length) {
        const list = document.createElement('ul');
        for (const error of errors) {
          const li = document.createElement('li'), link = document.createElement('a');
          link.href = `#${error.target.id || error.target.closest('section').id}`; link.textContent = error.text;
          link.addEventListener('click', event => { event.preventDefault(); error.range ? error.range.focus() : error.target.focus(); });
          li.append(link); list.append(li);
        }
        content.replaceChildren(list); if (focus) box.focus();
      }
      return !errors.length;
    }
    async function save(review) {
      if (saving || uncertain) return;
      if (root.dataset.persisted === 'true' && !dirty()) { saveFeedback.textContent = 'Your changes are already saved.'; if (review) api.review(); return; }
      if (!validation()) { saveFeedback.textContent = 'Complete the highlighted setup before saving.'; return; }
      const data = new FormData(form);
      const finish = window.ActionFeedback?.start(form, {button: root.querySelector(review ? '[data-review-program]' : '[data-save-draft]'), label: 'Saving program…'});
      saving = true; form.inert = true; form.setAttribute('aria-busy','true');
      saveFeedback.textContent = root.dataset.persisted === 'true' ? 'Updating program…' : 'Saving private draft…';
      try {
        const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', cache: 'no-store', headers: {'X-Program-Builder': '1'}});
        if (response.redirected) throw new Error('Your session may have expired. Open the portfolio in a new tab to check before retrying.');
        if (response.status === 403) throw new Error('Access could not be confirmed. Open the portfolio in a new tab to check your session and permissions.');
        if (response.status === 409) throw new Error('This program changed. Open it from the portfolio before trying again.');
        if (!response.ok) throw new Error('The save could not be confirmed. Check the portfolio before trying again.');
        const parsed = new DOMParser().parseFromString(await response.text(), 'text/html'), incoming = parsed.querySelector('[data-program-builder]');
        if (!incoming) throw new Error('The save could not be confirmed. Check the portfolio before trying again.');
        const y = scrollY, next = document.importNode(incoming, true);
        active.destroy(); root.replaceWith(next); active = setup(next);
        const location = parsed.querySelector('[data-builder-location]');
        if (location) document.querySelector('[data-builder-location]')?.replaceWith(document.importNode(location, true));
        document.title = parsed.title;
        if (next.dataset.saved === 'true') {
          history.replaceState({}, '', next.dataset.editUrl);
          if (review) active.review();
          else { scrollTo({top: y, behavior: 'instant'}); next.querySelector('[data-save-draft]').focus({preventScroll: true}); }
        } else next.querySelector('[data-validation-summary]').focus();
      } catch (error) {
        uncertain = true;
        saveFeedback.textContent = error instanceof TypeError ? 'The save could not be confirmed. Check the portfolio in a new tab before trying again.' : error.message;
        root.querySelector('[data-save-draft]').disabled = true; root.querySelector('[data-review-program]').disabled = true;
      } finally { finish?.(); saving = false; form.inert = false; form.removeAttribute('aria-busy'); }
    }
    form.noValidate = true;
    const selectAll = root.querySelector('[data-select-all-disabilities]');
    selectAll?.addEventListener('click', () => {
      form.querySelectorAll('[name=eligible_disability_types]:not(:disabled)').forEach(input => { input.checked = true; });
      update();
    });
    root.querySelectorAll('.builder-js-only').forEach(node => { node.hidden = false; });
    renumberQuestions();
    for (const [name, range] of window.SantolanScheduleCalendar(root.querySelector('[data-shared-calendar]'), form, update)) ranges.set(name, range);
    initial = root.dataset.bound === 'true' ? '' : serial(); update();
    form.addEventListener('input', event => { if (event.target.checkValidity?.()) event.target.removeAttribute('aria-invalid'); update(); });
    form.addEventListener('change', update);
    form.addEventListener('submit', event => { event.preventDefault(); save(false); });
    root.querySelector('[data-review-program]').addEventListener('click', () => {
      if (root.dataset.persisted === 'true' && !dirty()) { if (!saving && !uncertain) api.review(); }
      else save(true);
    });
    root.querySelector('[data-add-question]')?.addEventListener('click', () => {
      const rows = root.querySelector('[data-question-rows]');
      if (rows.children.length >= 50) return;
      rows.append(root.querySelector('[data-question-template]').content.cloneNode(true)); renumberQuestions(); update();
      rows.lastElementChild.querySelector('[name$="-label"]').focus();
      root.querySelector('[data-question-feedback]').textContent = `Requirement ${rows.children.length} added.`;
    });
    root.addEventListener('click', event => {
      const errorLink = event.target.closest('[data-error-field]');
      if (errorLink) {
        const field = form.elements.namedItem(errorLink.dataset.errorField);
        const rangeName = field?.closest?.('[data-native-dates]')?.dataset.nativeDates;
        if (rangeName && ranges.has(rangeName)) {
          event.preventDefault(); ranges.get(rangeName).focus();
        } else if (field?.focus) {
          event.preventDefault(); field.focus();
        }
      }
      const remove = event.target.closest('[data-remove-question]');
      if (remove) {
        remove.closest('[data-question]').remove(); renumberQuestions(); update();
        root.querySelector('[data-add-question]').focus(); root.querySelector('[data-question-feedback]').textContent = 'Requirement removed.';
      }
    });
    const setStep = id => root.querySelectorAll('.builder-steps > a').forEach(link => {
      if (link.hash === `#${id}`) link.setAttribute('aria-current','step'); else link.removeAttribute('aria-current');
    });
    const sections = [...root.querySelectorAll('.builder-section[id]')];
    const navigation = new AbortController();
    let clickedSection = null, framePending = false;
    function updateStep() {
      framePending = false;
      if (navigation.signal.aborted) return;
      // Keep the selected destination through smooth scrolling, even when the
      // page ends before that section can align with the top of the viewport.
      if (clickedSection) { setStep(clickedSection); return; }
      const margin = parseFloat(getComputedStyle(sections[0]).scrollMarginTop) || 0;
      const padding = parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop) || 0;
      const anchor = margin + padding;
      let current = sections[0];
      for (const section of sections) {
        if (section.getBoundingClientRect().top <= anchor + 2) current = section;
      }
      if (scrollY > 0 && scrollY + innerHeight >= document.documentElement.scrollHeight - 2) current = sections.at(-1);
      setStep(current.id);
    }
    function queueStep() {
      if (!framePending) { framePending = true; requestAnimationFrame(updateStep); }
    }
    function followManualScroll() { clickedSection = null; queueStep(); }
    const options = {passive: true, signal: navigation.signal};
    on(window, 'scroll', queueStep, options);
    on(window, 'resize', queueStep, options);
    on(window, 'wheel', followManualScroll, options);
    on(window, 'touchmove', followManualScroll, options);
    on(window, 'pointerdown', event => {
      if (event.target === document.documentElement) followManualScroll();
    }, options);
    on(window, 'keydown', event => {
      if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)
          && !event.target.closest('input,select,textarea,[contenteditable]')) followManualScroll();
    }, {signal: navigation.signal});
    root.querySelectorAll('.builder-steps > a').forEach(link => link.addEventListener('click', event => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      clickedSection = link.hash.slice(1); setStep(clickedSection);
    }));
    queueStep();
    const api = {dirty: () => saving || dirty(), destroy: () => navigation.abort(), review: () => {
      reviewed = true; const panel = root.querySelector('[data-review-ready]'); panel.hidden = false; panel.focus();
      panel.querySelector('[data-open-review]').href = root.dataset.reviewUrl;
    }};
    return api;
  }
  active = setup(document.querySelector('[data-program-builder]'));
  addEventListener('beforeunload', event => { if (active.dirty()) { event.preventDefault(); event.returnValue = ''; } });
})();

});
