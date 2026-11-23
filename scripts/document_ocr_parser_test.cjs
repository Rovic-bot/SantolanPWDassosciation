const assert = require('node:assert/strict');
const {test} = require('node:test');
const {extract, dateValue, fromResult, merge} = require('../static/js/document-ocr-parser.js');

test('reads explicitly labelled PWD details and preserves leading zeroes', () => {
  const {values} = extract('PWD ID No: 00-1234-001-0000042\nLast Name: DELA CRUZ\nFirst Name: JUAN MIGUEL\nMiddle Name: SANTOS\nDate of Birth: 21 January 1990\nSex: Male\nAddress: 123 Mabini Street, Barangay Santolan, Pasig City, NCR\nMobile number: 09171234567');
  assert.equal(values.last_name, 'DELA CRUZ');
  assert.equal(values.first_name, 'JUAN MIGUEL');
  assert.equal(values.birthdate, '1990-01-21');
  assert.equal(values.pwd_number, '00-1234-001-0000042');
  assert.equal(values.house_street, '123 Mabini Street');
  assert.equal(values.barangay, 'Santolan');
  assert.equal(values.city, 'Pasig City');
  assert.equal(values.contact_number, '09171234567');
});
test('reads bilingual National ID labels with values on following lines', () => {
  const {values} = extract('Apelyido / Last Name\nDELA CRUZ\nMga Pangalan / Given Names\nMARIA ANA\nGitnang Apelyido / Middle Name\nREYES\nPetsa ng Kapanganakan / Date of Birth\nMARCH 15 1985\nKasarian / Sex\nFEMALE');
  assert.equal(values.last_name, 'DELA CRUZ'); assert.equal(values.first_name, 'MARIA ANA');
  assert.equal(values.middle_name, 'REYES'); assert.equal(values.birthdate, '1985-03-15'); assert.equal(values.sex, 'Female');
});
test('receipts extract customer details without merchant or payment identifiers', () => {
  const {values} = extract('Name: A STORE\nAddress: STORE ADDRESS\nEmail: store@example.test\nTel: 0281234567\nReceipt No: 1234\nCustomer: CRUZ, ANA\nCustomer Address: 27 Test Street, Barangay Santolan, Pasig City\nCustomer Mobile: 09171234567\nTotal: 500', 'receipt');
  assert.equal(values.last_name, 'CRUZ'); assert.equal(values.first_name, 'ANA');
  assert.equal(values.contact_number, '09171234567'); assert.equal(values.house_street, '27 Test Street');
  assert.equal(values.pwd_number, undefined); assert.equal(values.email, undefined);
});
test('does not interpret a National ID, receipt or arbitrary number as a PWD ID', () => {
  for (const text of ['ID Number: 001234567', 'National ID: 001234567', 'Receipt No: 001234567', '001234567']) {
    assert.equal(extract(text).values.pwd_number, undefined);
  }
});
test('does not repair uncertain OCR characters in identifiers', () => {
  assert.equal(extract('PWD No: OO-1234-I23').values.pwd_number, undefined);
});
test('rejects invalid, ambiguous and future dates', () => {
  for (const date of ['02/03/1990', '31/02/1990', '2030-01-01', 'January 32 1990', '1990-13-01', '1/1/99']) assert.equal(dateValue(date), '', date);
  assert.equal(dateValue('29/02/2000'), '2000-02-29'); assert.equal(dateValue('12/25/1990'), '1990-12-25');
});
test('conflicting labels are omitted and produce a review note', () => {
  const result = extract('First Name: ANA\nFirst Name: JOSE');
  assert.equal(result.values.first_name, undefined); assert(result.notes.length);
});
test('does not invent missing personal or assessment information', () => {
  assert.deepEqual(extract('OFFICIAL RECEIPT\nTOTAL 500').values, {});
  assert.deepEqual(extract('Income: 500\nDisability: Visual\nApproved: Yes\nacknowledgement: true').values, {});
});
test('does not use a parent name or another ID issue date for the applicant', () => {
  assert.equal(extract('First name of father: JOSE').values.first_name, undefined);
  assert.equal(extract('Name of mother: MARIA').values.full_name, undefined);
  assert.equal(extract('Date issued: 2020-10-21\nNational ID: 123456789').values.date_issued, undefined);
  assert.equal(extract('PWD No: 00-1234-001-0000042\nDate issued: 2020-10-21').values.date_issued, '2020-10-21');
});
test('names and uncertain addresses remain available without guessing their divisions', () => {
  const {values, notes} = extract('Name: ANA MARIA DE LOS SANTOS\nAddress: 12 Test St, Santolan, Pasig');
  assert.equal(values.full_name, 'ANA MARIA DE LOS SANTOS'); assert.equal(values.first_name, undefined);
  assert.equal(values.house_street, undefined); assert(notes.length);
});
test('bilingual National ID labels work without separator slashes', () => {
  assert.equal(extract('GITNANG APELYIDOMIDDLE NAME\nSANTOS').values.middle_name,'SANTOS');
  const {values} = extract('Philippine National ID\nAPELYIDO LAST NAME\nREYES\nMGA PANGALAN GIVEN NAMES\nANA MARIA\nGITNANG APELYIDO MIDDLE NAME\nSANTOS\nPETSA NG KAPANGANAKAN DATE OF BIRTH\nMay 14, 1988\nTIRAHAN ADDRESS\n88 Example Street, Demo Barangay, CITY OF EXAMPLE, NCR, SECOND DISTRICT, PHILIPPINES, 1234');
  assert.equal(values.last_name, 'REYES'); assert.equal(values.first_name, 'ANA MARIA');
  assert.equal(values.middle_name, 'SANTOS'); assert.equal(values.birthdate, '1988-05-14');
  assert.equal(values.house_street, '88 Example Street'); assert.equal(values.barangay, 'Demo Barangay');
  assert.equal(values.city, 'CITY OF EXAMPLE'); assert.equal(values.region, 'NCR'); assert.equal(values.zip_code, '1234');
  assert.equal(values.pwd_number, undefined);
});
function line(text, x, y, confidence = 95, height = 14) {
  return {text, confidence, bbox: {x0:x, y0:y, x1:x+Math.max(40,text.length*7), y1:y+height},
    words:text.split(' ').map(text => ({text, confidence}))};
}
test('uses aligned label/value geometry instead of portrait and QR reading order', () => {
  const lines = [line('APELYIDO/LAST NAME',300,100),line('WRONG PERSON',25,120),line('REYES',300,122),
    line('MGA PANGALAN/GIVEN NAMES',300,165),line('QR NOISE',600,181),line('ANA MARIA',300,190),
    line('GITNANG APELYIDO/MIDDLE NAME',300,230),line('+',50,250,31),line('SANTOS',300,255),
    line('PETSA NG KAPANGANAKAN/DATE OF BIRTH',300,290),line('[=]',700,310),line('May 14, 1988',300,315),
    line('TIRAHAN/ADDRESS',80,380),line('88 Example Street, Demo Barangay, CITY OF EXAMPLE, NCR,',80,405),
    line('SECOND DISTRICT, PHILIPPINES, 1234',80,427),line('Enlarge QR',600,440)];
  const result=fromResult({text:lines.map(line=>line.text).join('\n'),blocks:[{paragraphs:[{lines}]}]});
  assert.equal(result.values.last_name, 'REYES'); assert.equal(result.values.first_name, 'ANA MARIA');
  assert.equal(result.values.middle_name, 'SANTOS'); assert.equal(result.values.birthdate, '1988-05-14');
  assert.equal(result.values.house_street, '88 Example Street'); assert.equal(result.values.zip_code, '1234');
  assert(!result.values.address.includes('Enlarge')); assert(result.regions.address); assert(result.nationalId);
});
test('drops weak one-letter graphics without deleting a confident name initial', () => {
  const address=line('SECOND DISTRICT, PHILIPPINES, 1234 j',80,450);
  address.words[address.words.length-1].confidence=55;
  const lines=[line('GITNANG APELYIDO/MIDDLE NAME',300,230),line('A.',300,255),
    line('TIRAHAN/ADDRESS',80,380),line('88 Example Street, Demo Barangay, CITY OF EXAMPLE, NCR,',80,410), address];
  const result=fromResult({text:'Philippine National ID',blocks:[{paragraphs:[{lines}]}]});
  assert.equal(result.values.middle_name,'A.'); assert.equal(result.values.zip_code,'1234');
});
test('geometry leaves absent values empty rather than borrowing from the next field', () => {
  const lines=[line('APELYIDO/LAST NAME',300,100),line('MGA PANGALAN/GIVEN NAMES',300,130),line('ANA MARIA',300,154)];
  const result=fromResult({text:'Philippine National ID',blocks:[{paragraphs:[{lines}]}]});
  assert.equal(result.values.last_name,undefined); assert.equal(result.values.first_name,'ANA MARIA');
});
test('retains complete bilingual labels containing a low-confidence known word', () => {
  const label = line('PETSA NG KAPANGANAKAN/DATE OF BIRTH', 300, 290, 83);
  label.words[2].confidence = 39;
  const lines = [label, line('May 14, 1988', 300, 315)];
  const result = fromResult({text: lines.map(item => item.text).join('\n'), blocks: [{paragraphs: [{lines}]}]});
  assert.equal(result.values.birthdate, '1988-05-14');
  assert.equal(result.matchedLabels, 1);
});

test('PWD captions can sit below values, with dates in separate columns', () => {
  const lines = [line('ID NO.', 25, 100), line('00-1234-001-0000042', 100, 90),
    line('NAME:', 25, 155), line('JUAN M. DELA CRUZ', 100, 145),
    line('PHYSICAL DISABILITY(ORTHO)', 25, 195), line('TYPE OF DISABILITY', 100, 225),
    line('08-22-67/56', 25, 280), line('01-24-2024', 250, 280),
    line('DATE OF BIRTH / AGE', 25, 310), line('DATE OF ISSUE', 250, 310),
    line('08-22-2029', 250, 360), line('EXPIRY DATE', 250, 390)];
  const {values} = fromResult({text: lines.map(l => l.text).join('\n'), blocks:[{paragraphs:[{lines}]}]}, 'pwd-front');
  assert.equal(values.pwd_number, '00-1234-001-0000042');
  assert.equal(values.first_name, 'JUAN'); assert.equal(values.middle_name, 'M.'); assert.equal(values.last_name, 'DELA CRUZ');
  assert.equal(values.birthdate, '1967-08-22'); assert.equal(values.date_issued, '2024-01-24');
  assert.equal(values.expiry_date, undefined); assert.equal(values.disability_type, 'PHYSICAL DISABILITY(ORTHO)');
});

test('PWD back distinguishes emergency contact and splits an explicitly named locality', () => {
  const {values} = extract('Address: 27 TEST STREET Santolan, Pasig City\nSex: Male\nBlood type: (OPTIONAL)\nParent/Guardian: ANA S. REYES\nCONTACT NO: 09171234567', 'pwd-back');
  assert.equal(values.house_street, '27 TEST STREET'); assert.equal(values.barangay, 'Santolan');
  assert.equal(values.city, 'Pasig City'); assert.equal(values.sex, 'Male');
  assert.equal(values.guardian_name, 'ANA S. REYES'); assert.equal(values.guardian_contact, '09171234567');
  assert.equal(values.contact_number, undefined); assert.equal(values.blood_type, undefined); assert.equal(values.full_name, undefined);
});

test('generic IDs do not copy emergency contacts as applicant contact numbers', () => {
  const {values} = extract('Name: CRUZ, JUAN\nIN CASE OF EMERGENCY NOTIFY:\nCONTACT NO: 09171234567');
  assert.equal(values.contact_number, undefined); assert.equal(values.guardian_contact, '09171234567');
});

test('PWD two-digit birth years require consistent age and issue date', () => {
  assert.equal(extract('Date of birth / age: 08-22-67', 'pwd-front').values.birthdate, undefined);
  assert.equal(extract('Date of birth / age: 08-22-67/12\nDate of issue: 01-24-2024', 'pwd-front').values.birthdate, undefined);
  assert.equal(extract('Date of birth / age: 08-22-1967/56', 'pwd-front').values.birthdate, '1967-08-22');
});

test('merging sides retains complementary fields and omits persistent conflicts', () => {
  const combined = merge([extract('Name: JUAN M. CRUZ\nPWD No: 00-0000-000-0000001', 'pwd-front'),
    extract('Address: 27 TEST STREET Santolan, Pasig City\nContact No: 09171234567', 'pwd-back')]);
  assert.equal(combined.values.first_name, 'JUAN'); assert.equal(combined.values.guardian_contact, '09171234567');
  const conflict = merge([{values:{full_name:'JUAN M. CRUZ',first_name:'JUAN'}}, {values:{full_name:'JOSE M. CRUZ'}}, {values:{full_name:'JUAN M. CRUZ'}}]);
  assert.equal(conflict.values.full_name, undefined); assert.equal(conflict.values.first_name, undefined); assert(conflict.notes.length);
});

test('city government header is not an applicant city', () => {
  assert.equal(extract('CITY GOVERNMENT OF PASIG\nName: JUAN M. CRUZ', 'pwd-front').values.city, undefined);
});

test('uncertain address readings keep derived fields marked for explicit review', () => {
  const result = merge([{values:{address:'27 TEST STREET, Pasig City',house_street:'27 TEST STREET',city:'Pasig City'},uncertain:['address']}]);
  assert(result.uncertain.includes('house_street')); assert(result.uncertain.includes('city'));
});

test('a blank PWD name is not filled with the next disability value', () => {
  const lines = [line('NAME:',25,100),line('PHYSICAL DISABILITY',25,130),line('TYPE OF DISABILITY',60,160)];
  assert.equal(fromResult({blocks:[{paragraphs:[{lines}]}]}, 'pwd-front').values.full_name, undefined);
});
