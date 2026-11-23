/* Conservative transcription helpers. OCR is a suggestion, never verification. */
(function (root) {
  'use strict';
  const labels = {
    last_name: ['last name', 'surname', 'family name', 'apelyido'],
    first_name: ['first name', 'given names?', 'mga pangalan', 'pangalan'],
    middle_name: ['middle name', 'gitnang apelyido'], suffix: ['suffix'],
    full_name: ['full name', 'name', 'pangalan'],
    birthdate: ['date of birth', 'birth ?date', 'birthday', 'dob', 'petsa ng kapanganakan', 'kapanganakan'],
    house_street: ['house no\\.? and street(?: name)?', 'house and street', 'street address'],
    address: ['residen(?:tial|ce) address', 'address', 'tirahan'],
    barangay: ['barangay', 'brgy\\.?'], city: ['city(?: / municipality)?', 'municipality', 'lungsod'],
    province: ['province', 'lalawigan'], region: ['region'], zip_code: ['zip(?: code)?', 'postal code'],
    contact_number: ['mobile(?: nos?\\.?)?', 'mobile number', 'contact (?:number|no\\.?)', 'telephone', 'tel\\.?'],
    email: ['email(?: address)?', 'e-mail(?: address)?'],
    sex: ['sex', 'gender', 'kasarian'], civil_status: ['civil status', 'marital status'],
    nationality: ['nationality', 'citizenship'],
    pwd_number: ['pwd (?:id )?(?:number|no\\.?)', 'pwd id'],
    date_issued: ['pwd id date issued', 'date issued', 'date of issue'],
    philhealth_number: ['philhealth (?:id )?(?:number|no\\.?)'],
    voter_certification_number: ['vrr(?: number| no\\.?)?', "voter'?s? certifi(?:cate|cation) (?:number|no\\.?)"],
    sss_number: ['sss (?:number|no\\.?)'], gsis_number: ['gsis (?:number|no\\.?)'],
    psn_number: ['psn (?:number|no\\.?)', 'philsys number'],
  };
  const receiptLabels = {
    full_name: ['customer(?: name)?', 'recipient(?: name)?', 'applicant(?: name)?', 'billed to', 'sold to', 'received from'],
    address: ['customer address', 'recipient address', 'billing address', 'residential address'],
    email: ['customer email', 'recipient email', 'applicant email'],
    contact_number: ['customer (?:mobile|phone|contact number)', 'recipient (?:mobile|phone|contact number)'],
    birthdate: labels.birthdate,
  };
  const clean = value => String(value || '').replace(/[\u0000-\u0008\u000b-\u001f]/g, '').replace(/[ \t]+/g, ' ').trim();
  const pwdLabels = {
    pwd_number: ['[i1l]\\s*d\\.?\\s*(?:number|no\\.?)', ...labels.pwd_number],
    birthdate: ['date\\s*of\\s*birth(?:\\s*/\\s*age)?', 'birth\\s*/\\s*age', ...labels.birthdate],
    disability_type: ['type of disability'],
    guardian_name: ['parent\\s*/\\s*guardian', 'parent or guardian', 'guardian', 'emergency contact name'],
    guardian_contact: ['emergency contact (?:number|no\\.?)', 'guardian contact (?:number|no\\.?)'],
    blood_type: ['blood type'],
    date_issued: ['[dp]ate\\s*(?:of|ors)\\s*issue', ...labels.date_issued],
    expiry_date: ['expiry date', 'expiration date'],
  };
  function dateValue(value) {
    const raw = clean(value).replace(/,/g, '');
    let year, month, day, found;
    if ((found = raw.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/))) {
      [, year, month, day] = found;
    } else if ((found = raw.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/))) {
      const a = Number(found[1]), b = Number(found[2]);
      if (a <= 12 && b <= 12 && a !== b) return ''; // The document must disambiguate day/month.
      year = found[3]; month = a > 12 ? b : a; day = a > 12 ? a : b;
    } else {
      found = raw.match(/^(?:(\d{1,2})[ -]+([a-z]+)|([a-z]+)[ -]+(\d{1,2}))[ -]+(\d{4})$/i);
      if (!found) return '';
      day = found[1] || found[4]; year = found[5];
      const months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
      month = months.indexOf((found[2] || found[3]).slice(0, 3).toLowerCase()) + 1;
    }
    const d = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
    if (Number(year) < 1900 || d > new Date() || d.getUTCFullYear() !== Number(year) ||
        d.getUTCMonth() + 1 !== Number(month) || d.getUTCDate() !== Number(day)) return '';
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }
  function splitName(value) {
    // Comma notation explicitly identifies the surname. For other full names,
    // offer the name for manual assignment instead of guessing compound names.
    const parts = value.split(',').map(clean);
    if (parts.length !== 2 || !parts.every(Boolean)) return {};
    return {last_name: parts[0], first_name: parts[1]};
  }
  function labelMatcher(kind) {
    const source = kind === 'receipt' ? receiptLabels : kind.startsWith('pwd') ? {...labels, ...pwdLabels} : labels;
    const patterns = Object.entries(source).flatMap(([key, aliases]) =>
      aliases.map(alias => ({key, pattern: new RegExp(`^(?:${alias})(?=$|[\\s:：])\\s*[:：]?\\s*(.*)$`, 'i')})));
    return line => {
      if (kind === 'id') {
        const bilingual = [
          ['last_name', 'APELYIDO\\s*/?\\s*LAST\\s*NAME'],
          ['first_name', 'MGA\\s*PANGALAN\\s*/?\\s*GIVEN\\s*NAMES?'],
          ['middle_name', 'GITNANG\\s*APELYIDO\\s*/?\\s*MIDDLE\\s*NAME'],
          ['birthdate', 'PETSA\\s*NG\\s*KAPANGANAKAN\\s*/?\\s*DATE\\s*OF\\s*BIRTH'],
          ['address', 'TIRAHAN\\s*/?\\s*ADDRESS'],
        ];
        for (const [key, alias] of bilingual) {
          const found = line.match(new RegExp(`^(${alias})(?=$|[\\s:：])\\s*[:：]?\\s*(.*)$`, 'i'));
          if (found) return {key, value: clean(found[2]), labelText: found[1], bilingual: true};
        }
      }
      // Bilingual labels on National IDs: Apelyido / Last Name.
      const normalized = line.replace(/^([^:]+)\s*\/\s*([^:]+)(:.*)?$/, (all, left, right, rest) => {
        if (patterns.some(item => item.pattern.test(left.trim())) && patterns.some(item => item.pattern.test(right.trim()))) {
          return right.trim() + (rest || '');
        }
        return all;
      });
      let best = null;
      for (const item of patterns) {
        const found = normalized.match(item.pattern);
        const length = found ? found[0].length - found[1].length : 0;
        if (found && !/[:：]|^(?:of|and|ng)\b/i.test(found[1]) && (!best || length > best.length)) best = {
          key: item.key, value: clean(found[1]), length, labelText: normalized.slice(0, length).replace(/[:：]\s*$/, '').trim()};
      }
      return best;
    };
  }
  function extract(text, kind = 'id') {
    const matchLabel = labelMatcher(kind);
    const lines = String(text).slice(0, 30000).split(/\r?\n/).map(clean).filter(Boolean);
    const values = {}, conflicts = new Set();
    const put = (key, value) => {
      value = clean(value);
      if (!value || value.length > 500 || /[<>]/.test(value)) return;
      if (values[key] && values[key].toLowerCase() !== value.toLowerCase()) conflicts.add(key);
      else values[key] = value;
    };
    let emergency = kind === 'pwd-back';
    for (let index = 0; index < lines.length; index++) {
      if (/in case of emergency|parent\s*\/\s*guardian/i.test(lines[index])) emergency = true;
      const item = matchLabel(lines[index]);
      if (!item) continue;
      if (item.key === 'city' && /^government\b/i.test(item.value)) continue;
      if (emergency && item.key === 'contact_number') item.key = 'guardian_contact';
      let value = item.value;
      if (!value && lines[index + 1] && !matchLabel(lines[index + 1])) value = lines[++index];
      if (item.key === 'address') {
        while (index + 1 < lines.length && !matchLabel(lines[index + 1]) &&
               !/[:：]|\b(?:republic|signature|valid|expiry|issued|receipt|total|cash|tin)\b/i.test(lines[index + 1]) && value.length < 220) {
          value += `, ${lines[++index]}`;
        }
      }
      put(item.key, value);
    }
    conflicts.forEach(key => delete values[key]);
    const notes = [];
    if (kind.startsWith('pwd') && values.birthdate) {
      const stamped = values.birthdate.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})(?:\s*\/\s*(\d{1,3}))?$/);
      if (stamped) {
        const [, month, day, year, age] = stamped;
        let fullYear = year;
        if (year.length === 2) {
          const issued = dateValue(values.date_issued || '');
          const candidates = issued && age ? [1900 + Number(year), 2000 + Number(year)].filter(candidate => {
            const [iy, im, id] = issued.split('-').map(Number);
            return iy - candidate - (im < Number(month) || (im === Number(month) && id < Number(day)) ? 1 : 0) === Number(age);
          }) : [];
          fullYear = candidates.length === 1 ? String(candidates[0]) : '';
        }
        values.birthdate = fullYear ? `${fullYear}-${month.padStart(2, '0')}-${day.padStart(2, '0')}` : '';
        if (year.length === 2) notes.push(values.birthdate ? 'Check the birth year inferred from the printed age and issue date.' : 'The two-digit birth year needs manual confirmation.');
      }
    }
    for (const key of ['birthdate', 'date_issued']) {
      if (values[key]) {
        const parsed = dateValue(values[key]);
        if (!parsed) notes.push('A date needs checking. Enter it manually using the date field.');
        values[key] = parsed;
      }
    }
    for (const key of ['pwd_number', 'philhealth_number', 'voter_certification_number', 'sss_number', 'gsis_number', 'psn_number', 'zip_code']) {
      if (values[key]) {
        const number = values[key].replace(/[–—]/g, '-').replace(/\s+/g, '');
        values[key] = /^[0-9]+(?:-[0-9]+)*$/.test(number) ? number : '';
      }
    }
    if (!values.pwd_number && !kind.startsWith('pwd')) delete values.date_issued;
    delete values.expiry_date;
    for (const key of ['contact_number', 'guardian_contact']) {
      if (!values[key]) continue;
      const number = values[key].replace(/[()\s-]/g, '').replace(/^\+63/, '0');
      values[key] = /^\d{7,15}$/.test(number) ? number : '';
    }
    if (values.blood_type && !/^(?:AB|A|B|O)[+-]$/i.test(values.blood_type)) delete values.blood_type;
    if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) values.email = '';
    if (values.sex) values.sex = /^(m|male|lalaki)$/i.test(values.sex) ? 'Male' : /^(f|female|babae)$/i.test(values.sex) ? 'Female' : '';
    for (const key of ['full_name', 'guardian_name']) if (values[key]) values[key] = values[key].replace(/^[^\p{L}]+|[^\p{L}.]+$/gu, '');
    if (values.full_name && !values.first_name && !values.last_name) {
      Object.assign(values, splitName(values.full_name));
      // An explicit middle initial provides a boundary without guessing where
      // multi-word given names or surnames begin and end.
      const initial = kind.startsWith('pwd') && values.full_name.match(/^([\p{L} .'-]+?)\s+([\p{L}]\.)\s+([\p{L} '-]+)$/u);
      if (initial) Object.assign(values, {first_name: initial[1], middle_name: initial[2], last_name: initial[3]});
      notes.push('Check how the full name is divided into first, middle and last names.');
    }
    if (values.address) {
      // Split only explicit comma-separated components, preserving uncertain text
      // for review instead of assuming every applicant lives in Santolan.
      const parts = values.address.split(',').map(clean).filter(Boolean);
      if (kind.startsWith('pwd') && parts.length >= 2 && /^Pasig City$/i.test(parts[1]) && /\sSantolan$/i.test(parts[0])) {
        values.barangay ||= 'Santolan';
        parts[0] = parts[0].replace(/\sSantolan$/i, '').trim();
      }
      const street = [], unmatched = [];
      const national = kind === 'id' && /pambansang\s+pagkakakilanlan|philippine\s+national\s+id|apelyido\s*\/?\s*last\s*name/i.test(text);
      const cityIndex = parts.findIndex(part => /^(?:city of\s+.+|.+\s+city)$/i.test(part));
      for (const [index, part] of parts.entries()) {
        if (/^(brgy\.?|barangay)\s+/i.test(part)) values.barangay ||= part.replace(/^(brgy\.?|barangay)\s+/i, '');
        else if (/^(?:city of\s+.+|.+\s+city)$/i.test(part)) values.city ||= part;
        else if (/^(NCR|National Capital Region|Metro Manila)$/i.test(part)) values.region ||= part;
        else if (/^\d{4}$/.test(part)) values.zip_code ||= part;
        else if (national && /^(?:philippines|(?:first|second|third|fourth|fifth|sixth|\d+(?:st|nd|rd|th)?)\s+district)$/i.test(part)) continue;
        else if (national && cityIndex === 2 && index === 1) values.barangay ||= part;
        else if (index === 0) street.push(part);
        else unmatched.push(part);
      }
      if (street.length && !unmatched.length) values.house_street ||= street.join(', ');
      else notes.push('Check the address and enter any missing barangay, city or street separately.');
    }
    if (conflicts.size) notes.push('Conflicting values were left out. Check the document and complete those fields manually.');
    return {values: Object.fromEntries(Object.entries(values).filter(([, value]) => value)), notes: [...new Set(notes)]};
  }
  function fromResult(result, kind = 'id', nationalContext = false) {
    if (kind.startsWith('pwd')) return fromPWDResult(result, kind);
    // Sparse-text OCR includes fragments from photographs, watermarks and QR
    // codes. Pair labels with nearby aligned text, never an unrelated fragment
    // merely because it happens to be next in the engine's reading order.
    const matchLabel = labelMatcher(kind);
    const lines = (result.blocks || []).flatMap(block => (block.paragraphs || []).flatMap(paragraph => paragraph.lines || []))
      .map(line => {
        const raw = clean(line.text), label = matchLabel(raw);
        // Preserve a complete known label even when an unfamiliar Filipino
        // word has a weak score. Personal values still use the word filter.
        const text = label && !label.value ? raw : line.words?.length ? line.words.filter(word => word.confidence >= 45 &&
          (!/^[\p{L}]{1,2}\.?$/u.test(word.text) || word.confidence >= 75)).map(word => word.text).join(' ') : line.text;
        return {...line, text: clean(text)};
      }).filter(line => line.bbox && line.confidence >= 55 && (/([\p{L}\p{N}]){2}/u.test(line.text) ||
        (/^[\p{L}]\.?$/u.test(line.text) && line.confidence >= 85)));
    if (!lines.length) return {...extract(result.text || '', kind), matchedLabels: 0};
    const labelled = lines.map(line => ({...line, label: matchLabel(line.text)}));
    const pairs = [], regions = {};
    const nationalId = kind === 'id' && (nationalContext || /pambansang\s+pagkakakilanlan|philippine\s+national\s+id|apelyido\s*\/?\s*last\s*name/i.test(result.text || ''));
    for (const anchor of labelled.filter(line => line.label)) {
      if (anchor.label.key === 'contact_number' && labelled.some(line =>
        /in case of emergency|parent\s*\/\s*guardian/i.test(line.text) && line.bbox.y0 < anchor.bbox.y0)) continue;
      let value = anchor.label.value;
      const height = Math.max(10, anchor.bbox.y1 - anchor.bbox.y0);
      const aligned = line => Math.abs(line.bbox.x0 - anchor.bbox.x0) <= Math.max(height * 2, 24);
      const lowerLabel = labelled.filter(line => line.label && line !== anchor && aligned(line) && line.bbox.y0 > anchor.bbox.y0 + height)
        .sort((a, b) => a.bbox.y0 - b.bbox.y0)[0];
      const candidates = labelled.filter(line => !line.label && aligned(line) &&
        (line.bbox.y0 + line.bbox.y1) / 2 > (anchor.bbox.y0 + anchor.bbox.y1) / 2 + height * .4 &&
        line.bbox.y0 < Math.min(anchor.bbox.y1 + height * 7, lowerLabel?.bbox.y0 ?? Infinity))
        .sort((a, b) => a.bbox.y0 - b.bbox.y0);
      const used = [anchor];
      if ((!value || anchor.label.bilingual) && candidates.length) {
        value = candidates[0].text;
        used.push(candidates[0]);
        if (anchor.label.key === 'address') {
          let previous = candidates[0];
          for (const line of candidates.slice(1, 3)) {
            if (line.bbox.y0 - previous.bbox.y1 > height * 3 ||
                /\b(?:digital id|signature|issued|expiry|valid|total|receipt|close|show back|enlarge)\b/i.test(line.text)) break;
            value += ` ${line.text}`; previous = line; used.push(line);
          }
        }
      }
      // Preserve the recognized label, including bilingual National ID context.
      if (value) {
        pairs.push(`${anchor.label.labelText}: ${value}`);
        regions[anchor.label.key] = {x0: Math.min(...used.map(line => line.bbox.x0)), y0: Math.min(...used.map(line => line.bbox.y0)),
          x1: Math.max(...used.map(line => line.bbox.x1)), y1: Math.max(...used.map(line => line.bbox.y1))};
      }
    }
    const text = (nationalId ? 'Philippine National ID\n' : '') + pairs.join('\n');
    const parsed = extract(text, kind);
    return {...parsed, matchedLabels: pairs.length, regions, nationalId};
  }
  function quality(parsed, confidence = 0) {
    const weights = {first_name: 4, last_name: 4, middle_name: 3, birthdate: 5, address: 3, full_name: 4};
    return Object.keys(parsed.values).reduce((sum, key) => sum + (weights[key] || 1), 0) + Math.max(0, confidence) / 100;
  }
  function fromPWDResult(result, kind) {
    const match = labelMatcher(kind);
    const rawLines = (result.blocks || []).flatMap(block => (block.paragraphs || []).flatMap(paragraph => paragraph.lines || []));
    if (!rawLines.length) return {...extract(result.text || '', kind), matchedLabels: 0};
    // Split distant columns, retaining their coordinates. Dates and their
    // captions often share an OCR line with the neighbouring date/signature.
    const lines = rawLines.flatMap(line => {
      if (!line.words?.every(word => word.bbox)) return [line];
      const groups = []; let group = [];
      for (const word of line.words) {
        const previous = group[group.length - 1];
        if (previous && word.bbox.x0 - previous.bbox.x1 > Math.max(28, (line.bbox.y1 - line.bbox.y0) * 1.2)) {
          groups.push(group); group = [];
        }
        group.push(word);
      }
      if (group.length) groups.push(group);
      return groups.map(words => ({text: words.map(word => word.text).join(' '),
        confidence: words.reduce((sum, word) => sum + word.confidence, 0) / words.length,
        bbox: {x0: Math.min(...words.map(word => word.bbox.x0)), y0: Math.min(...words.map(word => word.bbox.y0)),
          x1: Math.max(...words.map(word => word.bbox.x1)), y1: Math.max(...words.map(word => word.bbox.y1))}}));
    }).filter(line => line.bbox && line.confidence >= 35).map(line => ({...line, text: clean(line.text)}))
      .filter(line => /[\p{L}\p{N}]{2}/u.test(line.text));
    const labelled = lines.map(line => ({...line, label: match(line.text)}));
    const pairs = [], regions = {};
    const aboveKeys = new Set(['birthdate', 'date_issued', 'expiry_date', 'disability_type']);
    const usable = line => !line.label && !/\b(?:republic|government|affairs|office|signature|optional|mayor|notify|punishable|exclusive|privilege|valid|holder|benefits|transferable)\b/i.test(line.text);
    const fits = (key, text) => {
      if (['pwd_number', 'birthdate', 'date_issued', 'expiry_date'].includes(key)) return /^\d[\d\s./-]{4,}$/.test(text);
      if (['full_name', 'guardian_name'].includes(key)) return /^[\p{L}][\p{L}\s.,'’-]+$/u.test(text) && text.split(/\s+/).length >= 2;
      if (key === 'address') return text.split(/\s+/).length >= 2;
      if (key === 'disability_type') return /disability|ortho|physical|hearing|visual|speech|psychosocial|intellectual|learning|cancer|rare disease/i.test(text);
      return true;
    };
    for (const anchor of labelled.filter(line => line.label)) {
      const {key, labelText} = anchor.label;
      const box = anchor.bbox, height = Math.max(12, box.y1 - box.y0);
      let value = anchor.label.value, used = [anchor];
      if (value && !fits(key, value)) value = '';
      const center = line => (line.bbox.y0 + line.bbox.y1) / 2;
      if (!value) {
        const right = labelled.filter(line => usable(line) && fits(key, line.text) && line.bbox.x0 >= box.x1 - height &&
          Math.abs(center(line) - center(anchor)) < height * 3 && line.bbox.x0 - box.x1 < height * 14)
          .sort((a, b) => a.bbox.x0 - b.bbox.x0);
        const above = labelled.filter(line => usable(line) && fits(key, line.text) && line.bbox.y1 <= box.y0 + height * .35 &&
          box.y0 - line.bbox.y1 < height * 3.5 && line.bbox.x0 < box.x1 && line.bbox.x1 > box.x0 &&
          Math.abs((line.bbox.x0 + line.bbox.x1 - box.x0 - box.x1) / 2) < Math.max(box.x1 - box.x0, height * 4))
          .sort((a, b) => b.bbox.y1 - a.bbox.y1);
        const below = labelled.filter(line => usable(line) && fits(key, line.text) && line.bbox.y0 >= box.y1 &&
          line.bbox.y0 - box.y1 < height * 3 && Math.abs(line.bbox.x0 - box.x0) < height * 2)
          .sort((a, b) => a.bbox.y0 - b.bbox.y0);
        const candidate = aboveKeys.has(key) ? above[0] : right[0] || (!['full_name', 'pwd_number', 'guardian_name'].includes(key) && below[0]);
        if (candidate) { value = candidate.text; used.push(candidate); }
      }
      if (key === 'address' && value) {
        // The second address line is on the left; sex/blood type are on the right.
        const last = used[used.length - 1];
        const city = labelled.filter(line => usable(line) && /\bcity\b/i.test(line.text) &&
          line.bbox.y0 >= last.bbox.y1 && line.bbox.y0 - last.bbox.y1 < height * 7 &&
          line.bbox.x0 < box.x1 + height * 8).sort((a, b) => a.bbox.y0 - b.bbox.y0)[0];
        if (city && !/\bcity\b/i.test(value)) { value += `, ${city.text}`; used.push(city); }
      }
      if (value) {
        pairs.push(`${labelText}: ${value}`);
        regions[key] = {x0: Math.min(...used.map(line => line.bbox.x0)), y0: Math.min(...used.map(line => line.bbox.y0)),
          x1: Math.max(...used.map(line => line.bbox.x1)), y1: Math.max(...used.map(line => line.bbox.y1))};
      }
    }
    return {...extract(pairs.join('\n'), kind), matchedLabels: pairs.length, regions, pwdId: true};
  }
  function pwdRegions(results, kind, width, height) {
    const match = labelMatcher(kind), anchors = {};
    for (const result of results) for (const block of result.blocks || []) for (const paragraph of block.paragraphs || []) for (const line of paragraph.lines || []) {
      let label = match(clean(line.text)), box = line.bbox;
      // Use only the label's bounds when OCR joins its value onto the same line.
      for (let count = 1; count <= (line.words?.length || 0); count++) {
        const words = line.words.slice(0, count), candidate = match(words.map(word => word.text).join(' '));
        if (candidate && !candidate.value && words.every(word => word.bbox)) {
          label = candidate;
          box = {x0: Math.min(...words.map(word => word.bbox.x0)), y0: Math.min(...words.map(word => word.bbox.y0)),
            x1: Math.max(...words.map(word => word.bbox.x1)), y1: Math.max(...words.map(word => word.bbox.y1))};
        }
      }
      if (label && box && line.confidence >= 35 && (!anchors[label.key] || line.confidence > anchors[label.key].confidence)) {
        anchors[label.key] = {box, baseline: line.baseline, confidence: line.confidence};
      }
    }
    const front = kind !== 'pwd-back', type = anchors.disability_type?.box;
    const left = anchors.pwd_number?.box.x0 ?? anchors.full_name?.box.x0 ?? 0;
    const bodyRight = type ? Math.min(width, type.x0 + type.x1 - left) : width * .67;
    const regions = [];
    const heights = Object.values(anchors).map(({box, baseline}) => box.y1 - box.y0 -
      (baseline ? Math.abs(baseline.y1 - baseline.y0) : 0)).filter(value => value >= 12).sort((a, b) => a - b);
    const typicalHeight = heights[Math.floor(heights.length / 2)] || 30;
    const add = (key, x0, y0, x1, y1, anchor) => {
      const baseline = anchor?.baseline;
      const angle = baseline ? Math.atan2(baseline.y1 - baseline.y0, baseline.x1 - baseline.x0) * 180 / Math.PI : 0;
      const box = {x0: Math.max(0, Math.round(x0)), y0: Math.max(0, Math.round(y0)),
        x1: Math.min(width, Math.round(x1)), y1: Math.min(height, Math.round(y1))};
      if (box.x1 > box.x0 && box.y1 > box.y0) regions.push({key, ...box, angle: Math.abs(angle) < 8 ? angle : 0});
    };
    const above = new Set(['birthdate', 'date_issued', 'disability_type']);
    const right = new Set(front ? ['pwd_number', 'full_name'] : ['address', 'sex', 'guardian_name', 'contact_number', 'guardian_contact', 'blood_type']);
    for (const [key, anchor] of Object.entries(anchors)) {
      const box = anchor.box, h = Math.max(12, Math.min(typicalHeight * 1.15, box.y1 - box.y0));
      const bottom = anchor.baseline?.y0 ?? box.y1;
      if (above.has(key) && front) add(key, key === 'disability_type' ? left - h : box.x0 - h,
        bottom - h * 4.2, key === 'disability_type' ? bodyRight : Math.min(bodyRight, box.x1 + h * 2), bottom - h * 1.4, anchor);
      else if (right.has(key)) add(key === 'contact_number' ? 'guardian_contact' : key, box.x1 - h * .3,
        bottom - h * 3.5, front ? bodyRight : width * .88, bottom - h * .5, anchor);
      if (key === 'address' && !front) add('city_line', box.x1, bottom + h * .3,
        anchors.sex?.box.x0 ?? anchors.blood_type?.box.x0 ?? width * .55, bottom + h * 2.5, anchor);
      if (key === 'blood_type' && !front && !anchors.sex) add('sex_line', box.x0, bottom - h * 4.8, width * .88, bottom - h * 2, anchor);
    }
    return regions;
  }
  function merge(results) {
    const values = {}, notes = [], conflicts = new Set(), uncertain = new Set();
    for (const result of results) {
      notes.push(...(result.notes || []));
      (result.uncertain || []).forEach(key => uncertain.add(key));
      for (const [key, value] of Object.entries(result.values || {})) {
        if (values[key] && clean(values[key]).toLowerCase() !== clean(value).toLowerCase()) conflicts.add(key);
        else values[key] = value;
      }
    }
    // Conflicting full names must not leave derived name parts selected.
    if (conflicts.has('full_name')) ['first_name', 'middle_name', 'last_name'].forEach(key => conflicts.add(key));
    if (uncertain.has('address')) ['house_street', 'barangay', 'city', 'province', 'region', 'zip_code'].forEach(key => uncertain.add(key));
    conflicts.forEach(key => delete values[key]);
    if (conflicts.size) notes.push('The two sides contain conflicting details. These fields were left out; check that both images belong to the same person.');
    return {values, notes: [...new Set(notes)], uncertain: [...uncertain]};
  }
  const api = {extract, dateValue, fromResult, quality, merge, pwdRegions};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.DocumentOCRParser = api;
})(typeof window !== 'undefined' ? window : globalThis);
