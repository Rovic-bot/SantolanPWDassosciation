// Exercise decision-button validation without a browser, network, or real applicant.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const events = {};
const label = {textContent: 'Remarks'};
const notes = {name: 'notes', value: '', labels: [label], attributes: {},
  setAttribute(name, value) { this.attributes[name] = value; },
  setCustomValidity(value) { this.validationMessage = value; }};
const form = {id: 'eligibility-decision-form', elements: {notes}, dataset: {},
  matches: selector => selector === '[data-applicant-review-form]',
  reportValidity() { this.reported = true; }};
notes.form = form;
const document = {querySelectorAll: () => [], getElementById: () => null};
vm.runInNewContext(fs.readFileSync('static/js/admin-review.js', 'utf8'), {
  document, window: {}, location: {hash: ''},
  WorkspacePage: {run: callback => callback({
    on: (_, name, callback) => { events[name] = callback; },
    fetch: () => { throw new Error('No network requests are allowed in this validation check.'); },
  })},
});
events.DOMContentLoaded();

async function choose(outcome) {
  const button = {name: 'eligibility', value: outcome, form};
  await events.click({target: {closest: selector => selector === 'button[name="eligibility"]' ? button : null}});
  return button;
}

(async () => {
  for (const outcome of ['review', 'ineligible']) {
    notes.value = '   ';
    const button = await choose(outcome);
    assert.equal(notes.required, true);
    assert.equal(notes.attributes['aria-required'], 'true');
    assert.match(label.textContent, /required/);
    assert.ok(notes.validationMessage);
    await events.submit({target: form, submitter: button, preventDefault() {}});
    assert.equal(form.reported, true);
    assert.equal(form.dataset.saving, undefined);
    notes.value = 'Explain the missing information or the reason.';
    events.input({target: notes});
    assert.equal(notes.validationMessage, '');
  }
  notes.value = '';
  await choose('eligible');
  assert.equal(notes.required, false);
  assert.equal(notes.validationMessage, '');
  assert.match(label.textContent, /optional/);
  console.log('PASS: required explanations, whitespace rejection, blocked invalid submissions, and optional Eligible remarks; no network requests.');
})().catch(error => { console.error(error); process.exitCode = 1; });
