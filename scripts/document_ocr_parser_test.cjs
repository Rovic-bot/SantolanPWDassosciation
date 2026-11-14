const assert = require('node:assert/strict');
const {test} = require('node:test');
const {extract, dateValue} = require('../static/js/document-ocr-parser.js');

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
