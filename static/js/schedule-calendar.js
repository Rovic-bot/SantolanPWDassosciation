/* Shared accessible range calendar for programs, events and annual observances. */
(() => {
  'use strict';
  const pad = value => String(value).padStart(2, '0');
  const iso = date => `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
  const parse = value => new Date(`${value}T00:00:00Z`);
  const addDays = (value, amount) => { const day = parse(value); day.setUTCDate(day.getUTCDate() + amount); return iso(day); };
  const formatDay = value => new Intl.DateTimeFormat('en-PH', {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'}).format(parse(value));
  const todayParts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Manila'}).formatToParts(new Date()).map(part => [part.type, part.value]));
  const today = `${todayParts.year}-${todayParts.month}-${todayParts.day}`;

  /** Enhance named date ranges while preserving the original form fields. */
  function scheduleCalendar(panel, form, changed) {
    const picker = panel.querySelector('.builder-range-picker');
    const dateOnly = panel.dataset.dateOnly === 'true', annual = panel.dataset.annual === 'true';
    const firstDay = panel.dataset.initialMonth ? todayParts.year + '-' + pad(panel.dataset.initialMonth) + '-01' : today;
    const labelDay = value => annual ? new Intl.DateTimeFormat('en-PH', {month: 'short', day: 'numeric', timeZone: 'UTC'}).format(parse(value)) : formatDay(value);
    const fromTime = panel.querySelector('[data-start-time]'), toTime = panel.querySelector('[data-end-time]');
    const monthSelect = panel.querySelector('[data-calendar-month]'), yearSelect = panel.querySelector('[data-calendar-year]');
    const feedback = panel.querySelector('[data-range-feedback]'), states = new Map();
    for (const fields of panel.querySelectorAll('[data-native-dates]')) {
      const name = fields.dataset.nativeDates;
      const from = form.elements.namedItem(fields.dataset.startName), to = form.elements.namedItem(fields.dataset.endName);
      const start = from.value.slice(0, 10), end = to.value.slice(0, 10);
      states.set(name, {from, to, start, end, startTime: from.value.slice(11, 16) || '09:00',
        endTime: to.value.slice(11, 16) || '17:00', endpoint: start && !end ? 'end' : 'start',
        focusDay: start || firstDay, month: (start || firstDay).slice(0, 7) + '-01',
        emptyLabel: fields.dataset.rangeEmptyLabel,
        label: fields.dataset.rangeLabel || (name === 'registration' ? 'Registration window' : 'Program schedule'),
        accent: fields.dataset.rangeAccent || (name === 'registration' ? 'blue' : 'violet')});
      fields.hidden = true;
    }
    let selected = states.keys().next().value;
    const current = () => states.get(selected);
    const values = state => dateOnly ? [state.start, state.end] : [state.start && state.startTime ? `${state.start}T${state.startTime}` : '',
      state.end && state.endTime ? `${state.end}T${state.endTime}` : ''];
    const pending = state => { const [a,b] = values(state); return a !== state.from.value || b !== state.to.value; };
    const invalid = state => {
      const [a,b] = values(state);
      if (!state.start && !state.end) return state.from.required ? `Choose a start and end date for ${state.label.toLowerCase()}.` : '';
      if (dateOnly) {
        if (!a || !b) return 'Choose both the start and end dates.';
        if (annual && a.slice(5, 7) !== b.slice(5, 7)) return 'Choose an end date in the same observance month.';
        if ((annual ? b.slice(5) < a.slice(5) : b < a)) return 'The end date must be on or after the start date.';
        return '';
      }
      if (!a || !b) return panel.dataset.allowPartial === 'true' ? '' : 'Choose both dates and times.';
      if (b <= a) return 'The end date and time must be after the start.';
      return '';
    };
    const complete = state => !!state.from.value && !!state.to.value && !invalid(state) && !pending(state);
    const years = [1900, 2100, ...[...states.values()].flatMap(state => [state.start, state.end])
      .filter(Boolean).map(value => parse(value).getUTCFullYear())];
    const earliest = Math.min(...years), latest = Math.max(...years);
    for (let month = 0; month < 12; month++) monthSelect.add(new Option(new Intl.DateTimeFormat('en', {month: 'long', timeZone: 'UTC'}).format(new Date(Date.UTC(2026, month, 1))), String(month)));
    for (let year = earliest; year <= latest; year++) yearSelect.add(new Option(String(year), String(year)));
    picker.hidden = false;

    function refreshSummary() {
      const state = current(), issue = invalid(state);
      panel.dataset.accent = state.accent;
      for (const button of panel.querySelectorAll('[data-range]')) {
        const range = states.get(button.dataset.range);
        button.setAttribute('aria-pressed', String(button.dataset.range === selected));
        button.querySelector('[data-range-summary]').textContent = !range.start ?
          (range.emptyLabel || (!range.from.required ? 'Optional' : 'No dates selected')) :
          `${labelDay(range.start)}${range.end ? ` \u2013 ${labelDay(range.end)}` : ' \u00b7 Choose end date'}`;
      }
      for (const button of panel.querySelectorAll('[data-endpoint]')) {
        button.setAttribute('aria-pressed', String(button.dataset.endpoint === state.endpoint));
        button.disabled = button.dataset.endpoint === 'end' && !state.start;
      }
      panel.querySelector('[data-start-label]').textContent = state.start ? labelDay(state.start) : 'Choose date';
      panel.querySelector('[data-end-label]').textContent = state.end ? labelDay(state.end) : 'Choose date';
      panel.querySelector('[data-selection-help]').textContent = `${state.label}: ${state.start && state.end ? 'next click updates' : 'choose'} the ${state.endpoint} date.`;
      feedback.textContent = state.start && state.end && issue ? issue : '';
      for (const input of [fromTime, toTime].filter(Boolean)) input.setAttribute('aria-invalid', String(!!(state.start && state.end && issue)));
    }
    function render(focus = false) {
      const state = current(), shown = parse(state.month);
      monthSelect.value = String(shown.getUTCMonth()); yearSelect.value = String(shown.getUTCFullYear());
      panel.querySelector('[data-calendar-caption]').textContent = `${state.label}, ${new Intl.DateTimeFormat('en', {month: 'long', year: 'numeric', timeZone: 'UTC'}).format(shown)}`;
      panel.querySelector('[data-month-step="-1"]').disabled = shown.getUTCFullYear() === earliest && shown.getUTCMonth() === 0;
      panel.querySelector('[data-month-step="1"]').disabled = shown.getUTCFullYear() === latest && shown.getUTCMonth() === 11;
      const first = addDays(state.month, -((shown.getUTCDay() + 6) % 7)), fragment = document.createDocumentFragment();
      for (let week = 0; week < 6; week++) {
        const row = document.createElement('tr');
        for (let day = 0; day < 7; day++) {
          const value = addDays(first, week * 7 + day), date = parse(value), cell = document.createElement('td'), button = document.createElement('button');
          const labels = [formatDay(value)];
          let inActiveRange = false;
          for (const [name, range] of states) {
            const included = value === range.start || value === range.end || (range.start && range.end && value > range.start && value < range.end);
            if (!included) continue;
            const band = document.createElement('span');
            band.className = 'builder-date-band'; band.dataset.band = name;
            band.dataset.active = String(name === selected); band.setAttribute('aria-hidden', 'true');
            // Round every visible strip, including ranges continuing onto another week.
            if (day === 0 || value === range.start || !range.start) band.classList.add('band-start');
            if (day === 6 || value === range.end || !range.end) band.classList.add('band-end');
            cell.append(band);
            labels.push(`${range.label}, ${value === range.start ? 'start date' : ''}${value === range.start && value === range.end ? ' and ' : ''}${value === range.end ? 'end date' : ''}${value !== range.start && value !== range.end ? 'in range' : ''}`);
            if (name === selected) {
              inActiveRange = true; cell.classList.add('in-range');
              if (value === range.start) cell.classList.add('range-start');
              if (value === range.end) cell.classList.add('range-end');
            }
          }
          cell.setAttribute('aria-selected', String(inActiveRange));
          button.type = 'button'; button.dataset.date = value; button.textContent = String(date.getUTCDate());
          button.tabIndex = value === state.focusDay ? 0 : -1;
          button.disabled = date.getUTCFullYear() < earliest || date.getUTCFullYear() > latest;
          button.setAttribute('aria-label', labels.join(', '));
          if (value === today) { button.classList.add('is-today'); button.setAttribute('aria-current', 'date'); }
          if (date.getUTCMonth() !== shown.getUTCMonth()) button.classList.add('outside-month');
          cell.append(button); row.append(cell);
        }
        fragment.append(row);
      }
      panel.querySelector('[data-calendar-days]').replaceChildren(fragment);
      if (!panel.querySelector('[data-date][tabindex="0"]')) panel.querySelector(`[data-date="${state.month}"]`).tabIndex = 0;
      refreshSummary();
      if (focus) panel.querySelector(`[data-date="${state.focusDay}"]`)?.focus({preventScroll: true});
    }
    function selectRange(name) {
      selected = name;
      if (fromTime) fromTime.value = current().startTime;
      if (toTime) toTime.value = current().endTime;
      render();
    }
    function sync() {
      const state = current();
      // Never submit a previous valid range while the visible selection is incomplete/invalid.
      // Keep those original values until corrected; range validation blocks form submission.
      if (!invalid(state)) [state.from.value, state.to.value] = values(state);
      refreshSummary(); changed();
    }
    picker.addEventListener('click', event => {
      const mode = event.target.closest('[data-range]');
      if (mode) { selectRange(mode.dataset.range); return; }
      const endpoint = event.target.closest('[data-endpoint]');
      if (endpoint) { current().endpoint = endpoint.dataset.endpoint; refreshSummary(); return; }
      const state = current(), day = event.target.closest('[data-date]');
      if (event.target.closest('[data-clear-range]') && !state.from.required) {
        state.start = state.end = ''; state.endpoint = 'start'; render(); sync(); return;
      }
      if (day) {
        let value = day.dataset.date;
        if (annual && state.endpoint === 'end' && state.start) {
          // The display year is a calendar aid, not part of an annual schedule.
          const annualEnd = state.start.slice(0, 4) + value.slice(4);
          if (iso(parse(annualEnd)) !== annualEnd) {
            feedback.textContent = 'Choose the start and end dates in a year containing both dates.';
            return;
          }
          value = annualEnd;
        }
        if (!state.start || state.endpoint === 'start' || (!annual && value < state.start)) {
          state.start = value;
          if (annual || (state.end && state.end < value)) state.end = '';
          state.endpoint = 'end';
        } else { state.end = value; state.endpoint = 'start'; }
        state.focusDay = value; state.month = value.slice(0, 7) + '-01';
        render(true); sync();
      }
      const month = event.target.closest('[data-month-step]');
      if (month) {
        const shown = parse(state.month); shown.setUTCMonth(shown.getUTCMonth() + Number(month.dataset.monthStep));
        state.month = iso(shown); state.focusDay = state.month; render();
      }
    });
    picker.addEventListener('keydown', event => {
      const button = event.target.closest('[data-date]');
      if (!button) return;
      let next = button.dataset.date;
      const offsets = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7};
      if (event.key in offsets) next = addDays(next, offsets[event.key]);
      else if (event.key === 'Home') next = addDays(next, -((parse(next).getUTCDay() + 6) % 7));
      else if (event.key === 'End') next = addDays(next, 6 - ((parse(next).getUTCDay() + 6) % 7));
      else if (event.key === 'PageUp' || event.key === 'PageDown') {
        const date = parse(next), day = date.getUTCDate(); date.setUTCDate(1);
        date.setUTCMonth(date.getUTCMonth() + (event.key === 'PageUp' ? -1 : 1) * (event.shiftKey ? 12 : 1));
        const last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
        date.setUTCDate(Math.min(day, last)); next = iso(date);
      } else return;
      event.preventDefault();
      if (parse(next).getUTCFullYear() < earliest || parse(next).getUTCFullYear() > latest) return;
      current().focusDay = next; current().month = next.slice(0, 7) + '-01'; render(true);
    });
    for (const select of [monthSelect, yearSelect]) select.addEventListener('change', () => {
      current().month = iso(new Date(Date.UTC(Number(yearSelect.value), Number(monthSelect.value), 1)));
      current().focusDay = current().month; render();
    });
    const updateTimes = () => { current().startTime = fromTime.value; current().endTime = toTime.value; sync(); };
    for (const input of [fromTime, toTime].filter(Boolean)) {
      input.addEventListener('input', updateTimes); input.addEventListener('change', updateTimes);
    }
    selectRange(selected);
    return new Map([...states].map(([name, state]) => [name, {
      pending: () => pending(state), complete: () => complete(state), error: () => invalid(state),
      focus: () => { selectRange(name); panel.querySelector('[data-date][tabindex="0"]').focus(); }
    }]));
  }

  window.SantolanScheduleCalendar = scheduleCalendar;
})();
