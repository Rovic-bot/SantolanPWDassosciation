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
    const source = kind === 'receipt' ? receiptLabels : labels;
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
    for (let index = 0; index < lines.length; index++) {
      const item = matchLabel(lines[index]);
      if (!item) continue;
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
    if (!values.pwd_number) delete values.date_issued;
    if (values.contact_number) {
      const number = values.contact_number.replace(/[()\s-]/g, '').replace(/^\+63/, '0');
      values.contact_number = /^\d{7,15}$/.test(number) ? number : '';
    }
    if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) values.email = '';
    if (values.sex) values.sex = /^(m|male|lalaki)$/i.test(values.sex) ? 'Male' : /^(f|female|babae)$/i.test(values.sex) ? 'Female' : '';
    if (values.full_name && !values.first_name && !values.last_name) {
      Object.assign(values, splitName(values.full_name));
      notes.push('Check how the full name is divided into first, middle and last names.');
    }
    if (values.address) {
      // Split only explicit comma-separated components, preserving uncertain text
      // for review instead of assuming every applicant lives in Santolan.
      const parts = values.address.split(',').map(clean).filter(Boolean);
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
  const api = {extract, dateValue, fromResult, quality};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.DocumentOCRParser = api;
})(typeof window !== 'undefined' ? window : globalThis);
