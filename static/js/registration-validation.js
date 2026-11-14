/* Shared new-intake validation. No personal data is sent to a lookup service. */
WorkspacePage.run(({on, cleanup}) => {
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
      const list = document.createElement('datalist');
      list.id = input.id + '_addresses';
      input.setAttribute('list', list.id);
      input.after(list);
      lists[name] = list;
    }
    const options = (name, values) => {
      if (!lists[name]) return;
      lists[name].replaceChildren(...[...new Set(values)].map(value => {
        const option = document.createElement('option'); option.value = value; return option;
      }));
    };
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
      if (!city) { selected = null; rows = []; options('barangay', []); validate(); return; }
      if (autofill) {
        if (selected && selected.code !== city.code) inputs.barangay.value = '';
        inputs.city.value = city.value;
        inputs.region.value = city.region;
        if (inputs.province) inputs.province.value = provinceFor(city);
      }
      selected = city; rows = []; options('barangay', []);
      status.textContent = 'Loading barangays…';
      try {
        const data = await loadBarangays(city.code);
        if (run !== revision) return;
        rows = data; options('barangay', rows.map(row => row[1]));
        status.textContent = 'Choose a barangay in ' + city.name + '.';
        validate();
      } catch (error) {
        if (run !== revision || error.name === 'AbortError') return;
        status.textContent = 'Barangay suggestions could not load. Type the correct barangay; it will be checked when submitted.';
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
      if (error.name !== 'AbortError') status.textContent =
        'Address suggestions could not load. Type the full address; it will be checked when submitted. Reload to retry suggestions.';
    });
  });
});
