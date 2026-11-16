/* Shared new-intake validation. No personal data is sent to a lookup service. */
WorkspacePage.run(({on, cleanup, requestAnimationFrame}) => {
  const asset = document.querySelector('[data-registration-validation]');
  if (!asset) return;
  const base = asset.dataset.addressBase;
  const normalize = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/\s+/g, ' ');
  const aliases = city => {
    const name = normalize(city.name), short = name.replace(/^city of | city$/g, '');
    return [normalize(city.value), name, short, short + ' city'];
  };
  const regionAliases = name => [normalize(name), normalize(name.split(' (')[0]),
    ...[...name.matchAll(/\(([^)]+)\)/g)].map(match => normalize(match[1])),
    ...(name.includes('(NCR)') ? ['metro manila'] : [])];
  const provinceFor = city => city.province || (city.region_code === '1300000000' ?
    'Metro Manila (NCR - no province)' : 'Not applicable (independent city)');
  const controller = new AbortController();
  cleanup(() => controller.abort());
  let indexPromise;
  const loads = new Map();
  const read = url => fetch(url, {signal: controller.signal, credentials: 'same-origin'})
    .then(response => { if (!response.ok) throw new Error('Address list unavailable'); return response.json(); });
  const loadIndex = () => indexPromise ||= read(base + 'index.json');
  const loadBarangays = code => {
    if (!loads.has(code)) loads.set(code, read(base + code + '.json').catch(error => {loads.delete(code); throw error;}));
    return loads.get(code);
  };

  function addressMenu(input, initialMessage) {
    // Keep the original labelled input and submitted value. Only the suggestion
    // UI changes; geography and server-side validation use the same catalogue.
    const menu = document.createElement('div');
    menu.className = 'registration-address-menu';
    menu.hidden = true;
    menu.setAttribute('popover', 'manual');
    const list = document.createElement('ul');
    list.id = input.id + '_addresses';
    list.className = 'registration-address-list';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', (input.labels?.[0]?.textContent.trim() || input.name) + ' suggestions');
    list.setAttribute('translate', 'no');
    const message = document.createElement('p');
    message.className = 'registration-address-message';
    message.setAttribute('role', 'status');
    menu.append(list, message);
    document.body.append(menu);
    cleanup(() => menu.remove());
    input.removeAttribute('list');
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-haspopup', 'listbox');
    input.setAttribute('aria-controls', list.id);
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('autocomplete', 'off');
    input.spellcheck = false;
    let values = [], matches = [], active = -1, emptyMessage = initialMessage, framePending = false;

    function close() {
      if (menu.hidePopover && menu.matches(':popover-open')) menu.hidePopover();
      menu.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      active = -1;
    }
    function position() {
      if (menu.hidden) return;
      const box = input.getBoundingClientRect(), viewport = window.visualViewport;
      const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
      const width = viewport?.width || innerWidth, bottom = top + (viewport?.height || innerHeight);
      // Focus uses smooth scrolling on these forms. Keep tracking until the
      // field reaches the viewport, without drawing a detached menu meanwhile.
      if (box.bottom <= top || box.top >= bottom || box.right <= left || box.left >= left + width) {
        menu.style.visibility = 'hidden'; input.setAttribute('aria-expanded', 'false'); return;
      }
      const below = bottom - box.bottom - 14, above = box.top - top - 14;
      const upwards = below < 240 && above > below, room = Math.min(320, upwards ? above : below);
      if (room < 80) { menu.style.visibility = 'hidden'; input.setAttribute('aria-expanded', 'false'); return; }
      const menuWidth = Math.min(box.width, width - 16);
      menu.style.width = menuWidth + 'px';
      menu.style.left = Math.max(left + 8, Math.min(box.left, left + width - menuWidth - 8)) + 'px';
      menu.style.maxHeight = room + 'px';
      menu.style.top = (upwards ? box.top - 6 - menu.getBoundingClientRect().height : box.bottom + 6) + 'px';
      menu.style.visibility = 'visible';
      input.setAttribute('aria-expanded', 'true');
    }
    function schedulePosition() {
      if (menu.hidden || framePending) return;
      framePending = true;
      requestAnimationFrame(() => { framePending = false; position(); });
    }
    function render() {
      if (input.matches(':disabled') || input.readOnly) return;
      const terms = normalize(input.value).split(' ').filter(Boolean);
      const filtered = values.filter(item => terms.every(term => item.search.includes(term)));
      matches = filtered.slice(0, 50);
      active = -1;
      input.removeAttribute('aria-activedescendant');
      list.replaceChildren(...matches.map((item, index) => {
        const option = document.createElement('li');
        option.id = list.id + '_' + index;
        option.className = 'registration-address-option';
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', 'false');
        option.dataset.index = index;
        option.textContent = item.value;
        return option;
      }));
      list.scrollTop = 0;
      message.textContent = !values.length ? emptyMessage : !matches.length ?
        'No matching addresses. Check the spelling or try another name.' : filtered.length > matches.length ?
          'Showing 50 of ' + filtered.length + ' matches. Keep typing to narrow the list.' :
          filtered.length + (filtered.length === 1 ? ' matching address' : ' matching addresses');
      menu.hidden = false;
      if (menu.showPopover && !menu.matches(':popover-open')) menu.showPopover();
      input.setAttribute('aria-expanded', 'true');
      position();
    }
    function highlight(index) {
      active = index;
      [...list.children].forEach((option, item) => option.setAttribute('aria-selected', String(item === active)));
      const option = list.children[active];
      if (!option) { input.removeAttribute('aria-activedescendant'); return; }
      input.setAttribute('aria-activedescendant', option.id);
      // Scroll just the suggestion list, never the form or its section rail.
      const offset = option.offsetTop - list.offsetTop;
      if (offset < list.scrollTop) list.scrollTop = offset;
      else if (offset + option.offsetHeight > list.scrollTop + list.clientHeight)
        list.scrollTop = offset + option.offsetHeight - list.clientHeight;
    }
    function choose(index) {
      if (!matches[index]) return;
      input.value = matches[index].value;
      input.focus({preventScroll: true});
      input.dispatchEvent(new Event('input', {bubbles: true}));
      input.dispatchEvent(new Event('change', {bubbles: true}));
      close();
    }
    // Focus can scroll a field into view after its event handlers finish.
    on(input, 'focus', () => requestAnimationFrame(() => {
      if (document.activeElement === input && menu.hidden) render();
    }));
    on(input, 'click', () => { if (menu.hidden) render(); });
    on(input, 'input', () => { if (document.activeElement === input) render(); });
    on(input, 'blur', close);
    on(input, 'keydown', event => {
      if (event.isComposing || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (event.key === 'Escape') { if (!menu.hidden) { event.preventDefault(); close(); } return; }
      if (event.key === 'Tab') { close(); return; }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (menu.hidden) render();
        if (matches.length) highlight(active < 0 ? (event.key === 'ArrowDown' ? 0 : matches.length - 1) :
          Math.max(0, Math.min(matches.length - 1, active + (event.key === 'ArrowDown' ? 1 : -1))));
      } else if (event.key === 'Enter' && !menu.hidden && active >= 0) {
        event.preventDefault(); choose(active);
      }
    });
    // Retain input focus until click/tap selection; touch scrolling stays native.
    on(menu, 'pointerdown', event => { if (event.target.closest('[role="option"]')) event.preventDefault(); });
    on(menu, 'click', event => {
      const option = event.target.closest('[role="option"]');
      if (option) choose(Number(option.dataset.index));
    });
    on(document, 'pointerdown', event => { if (event.target !== input && !menu.contains(event.target)) close(); });
    on(document, 'scroll', event => { if (!menu.contains(event.target)) schedulePosition(); }, {capture: true, passive: true});
    on(window, 'resize', schedulePosition, {passive: true});
    if (window.visualViewport) {
      on(window.visualViewport, 'resize', schedulePosition, {passive: true});
      on(window.visualViewport, 'scroll', schedulePosition, {passive: true});
    }
    return {
      setValues(items, empty = 'No matching addresses. Check the spelling or try another name.') {
        values = [...new Set(items)].map(value => ({value, search: normalize(value)}));
        input.dataset.addressCount = values.length;
        emptyMessage = empty;
        if (!menu.hidden) render();
      },
    };
  }
  document.querySelectorAll('form:has([data-intake-today])').forEach(form => {
    const field = name => form.elements.namedItem(name);
    const mobileMessage = 'Enter 10 digits starting with 9, without the leading 0 or +63.';
    form.querySelectorAll('[data-ph-mobile]').forEach(input => {
      const clean = value => {
        let digits = value.replace(/\s/g, '');
        if (/^(?:\+63|63|0)9[0-9]{9}$/.test(digits)) digits = digits.replace(/^(?:\+63|63|0)/, '');
        return digits;
      };
      let previous = clean(input.value);
      if (/^9[0-9]{0,9}$/.test(previous) || !previous) input.value = previous;
      else previous = '';
      on(input, 'beforeinput', event => {
        if (event.data && /[^0-9]/.test(event.data)) event.preventDefault();
      });
      on(input, 'keydown', event => {
        if (event.ctrlKey || event.metaKey || event.altKey || event.key.length !== 1) return;
        if (!/^[0-9]$/.test(event.key) || (input.selectionStart === 0 && event.key !== '9')) event.preventDefault();
      });
      on(input, 'paste', event => {
        event.preventDefault();
        const pasted = clean(event.clipboardData?.getData('text') || '');
        const candidate = input.value.slice(0, input.selectionStart) + pasted + input.value.slice(input.selectionEnd);
        if (!/^9[0-9]{0,9}$/.test(candidate)) return;
        input.value = candidate;
        input.dispatchEvent(new Event('input', {bubbles: true}));
      });
      on(input, 'input', () => {
        const candidate = clean(input.value);
        if (/^9[0-9]{0,9}$/.test(candidate) || !candidate) { input.value = candidate; previous = candidate; }
        else input.value = previous;
      });
      input.title = mobileMessage;
    });

    const required = (name, needed) => {
      const input = field(name);
      if (!input) return;
      input.required = needed;
      const label = form.querySelector('label[for="' + input.id + '"]');
      if (label) {
        let marker = label.querySelector('[data-conditional-required]');
        if (!marker) {
          marker = document.createElement('span');
          marker.dataset.conditionalRequired = '';
          marker.textContent = ' (required)';
          marker.className = 'small';
          label.append(marker);
        }
        marker.hidden = !needed;
      }
    };
    const age = () => {
      const today = field('birthdate').dataset.intakeToday;
      const born = field('birthdate').value;
      return born ? Number(today.slice(0, 4)) - Number(born.slice(0, 4)) -
        Number(today.slice(5) < born.slice(5)) : null;
    };
    const ageChoices = [...form.querySelectorAll('[data-age-choices]')].map(input => ({
      input, choices: JSON.parse(input.dataset.ageChoices), allowed: JSON.parse(input.dataset.childValues), child: null,
    }));
    const restrictByAge = years => {
      ageChoices.forEach(item => {
        const child = years !== null && years <= Number(item.input.dataset.childMaxAge);
        if (child === item.child) return;
        const selected = item.input.value;
        const choices = item.choices.filter(([value]) => !child || !value || item.allowed.includes(value));
        item.input.replaceChildren(...choices.map(([value, label]) => new Option(label, value)));
        item.input.value = choices.some(([value]) => value === selected) ? selected : '';
        item.child = child;
      });
      if (field('application_type')) {
        const child = years !== null && years < 15;
        ['employment_category', 'employment_nature', 'occupation', 'occupation_other'].forEach(name => {
          const input = field(name);
          if (child) input.value = '';
          input.disabled = child;
        });
      }
    };
    const conditional = () => {
      const years = age();
      restrictByAge(years);
      const married = field('civil_status')?.value === 'Married';
      required('spouse_name', married); required('spouse_contact', married);
      const guardian = (years !== null && years < 18) || !!field('guardian_name')?.value || !!field('guardian_contact')?.value;
      required('guardian_name', guardian); required('guardian_contact', guardian);
      if (field('application_type')) {
        required('pwd_number', field('application_type').value === 'Renewal');
        const employed = field('employment_status').value === 'Employed';
        required('employment_category', employed); required('employment_nature', employed);
        required('occupation', employed || field('employment_status').value === 'Self employed');
        required('occupation_other', field('occupation').value === 'Other');
        const boxes = [...form.querySelectorAll('[name="disability_types"]')];
        boxes[0]?.setCustomValidity(boxes.some(box => box.checked) ? '' : 'Select at least one type of disability.');
      }
    };
    on(form, 'input', conditional); on(form, 'change', conditional);
    conditional();

    const inputs = Object.fromEntries(['city', 'barangay', 'province', 'region'].map(name => [name, field(name)]));
    const lists = {};
    for (const [name, input] of Object.entries(inputs)) {
      if (!input) continue;
      lists[name] = addressMenu(input, name === 'barangay' ? 'Select a city / municipality first.' : 'Loading address suggestions…');
    }
    const options = (name, values, message) => lists[name]?.setValues(values, message);
    const status = document.createElement('p');
    status.className = 'form-text'; status.setAttribute('role', 'status');
    inputs.city.after(status);
    let index, selected, rows = [], revision = 0;
    function matchCity() {
      const value = normalize(inputs.city.value);
      let matches = index.cities.filter(city => aliases(city).includes(value));
      const exact = matches.filter(city => normalize(city.value) === value);
      if (exact.length) matches = exact;
      if (matches.length > 1) matches = matches.filter(city => regionAliases(city.region).includes(normalize(inputs.region.value)));
      if (matches.length > 1 && inputs.province) matches = matches.filter(city => normalize(provinceFor(city)) === normalize(inputs.province.value));
      return matches.length === 1 ? matches[0] : null;
    }
    const validate = () => {
      if (!index) return; // The server still validates typed addresses if a download fails.
      const city = matchCity();
      inputs.city.setCustomValidity(inputs.city.value && !city ? 'Select a city / municipality from the address list.' : '');
      inputs.region.setCustomValidity(city && inputs.region.value && !regionAliases(city.region).includes(normalize(inputs.region.value)) ?
        'Choose ' + city.region + ' for this city / municipality.' : '');
      if (inputs.province) inputs.province.setCustomValidity(city && inputs.province.value &&
        normalize(inputs.province.value) !== normalize(provinceFor(city)) ? 'Choose ' + provinceFor(city) + ' for this city / municipality.' : '');
      inputs.barangay.setCustomValidity(city && selected?.code === city.code && rows.length && inputs.barangay.value &&
        !rows.some(row => normalize(row[1]) === normalize(inputs.barangay.value)) ? 'Select a barangay belonging to ' + city.name + '.' : '');
    };
    async function selectCity(autofill) {
      const run = ++revision, city = matchCity();
      if (!city) {
        selected = null; rows = []; options('barangay', [], 'Select a city / municipality first.');
        status.textContent = 'Type a city / municipality and select a matching suggestion.';
        validate(); return;
      }
      if (autofill) {
        if (selected && selected.code !== city.code) inputs.barangay.value = '';
        inputs.city.value = city.value;
        inputs.region.value = city.region;
        if (inputs.province) inputs.province.value = provinceFor(city);
      }
      selected = city; rows = []; options('barangay', [], 'Loading barangays…'); validate();
      status.textContent = 'Loading barangays…';
      try {
        const data = await loadBarangays(city.code);
        if (run !== revision) return;
        rows = data; options('barangay', rows.map(row => row[1]));
        status.textContent = 'Choose a barangay in ' + city.name + '.';
        validate();
      } catch (error) {
        if (run !== revision || error.name === 'AbortError') return;
        options('barangay', [], 'Suggestions could not load. You can still type the correct barangay.');
        status.textContent = 'Barangay suggestions could not load. Type the correct barangay; it will be checked when submitted.';
        validate();
      }
    }
    on(inputs.city, 'change', () => { if (index) selectCity(true); });
    on(inputs.city, 'input', () => { if (index) validate(); });
    on(inputs.barangay, 'input', validate); on(inputs.barangay, 'change', validate);
    for (const name of ['region', 'province']) if (inputs[name]) {
      on(inputs[name], 'input', validate);
      on(inputs[name], 'change', () => {
        if (!index) return;
        validate();
        if (!inputs[name].validity.valid) status.textContent = 'Address fields must match. Select the city to refill its region and province.';
      });
    }
    on(form, 'submit', () => { conditional(); validate(); }, {capture: true});
    status.textContent = 'Loading address suggestions…';
    loadIndex().then(data => {
      if (!form.isConnected) return;
      index = data;
      options('city', index.cities.map(city => city.value));
      options('region', index.regions.map(region => region.name));
      options('province', index.cities.map(provinceFor));
      status.textContent = 'Type a city / municipality and select a matching suggestion.';
      if (inputs.city.value) selectCity(false);
    }).catch(error => {
      if (error.name !== 'AbortError') {
        Object.keys(lists).forEach(name => options(name, [], 'Suggestions could not load. You can still type your address.'));
        status.textContent = 'Address suggestions could not load. Type the full address; it will be checked when submitted. Reload to retry suggestions.';
      }
    });
  });
});
