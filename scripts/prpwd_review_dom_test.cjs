// Browser API boundary checks without contacting the registry or submitting IDs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function check(blocked = false) {
  const events = {}, copied = [], locations = [], meta = [], buttons = [{}, {}];
  const number = {value: '00-0000-000-0000001', checkValidity: () => true,
    addEventListener: (name, action) => { events[name] = action; }};
  const opened = {value: ''}, feedback = {};
  const form = {elements: {namedItem: name => name === 'pwd_number' ? number : opened},
    querySelectorAll: () => buttons};
  const panel = {dataset: {prpwdUrl: 'https://registry.example.test/manual'}, closest: () => form,
    querySelector: name => name === '[data-prpwd-feedback]' ? feedback : {
      addEventListener: (name, action) => { events.open = action; }}};
  const popup = {opener: {}, document: {createElement: () => ({}), head: {append: node => meta.push(node)}},
    location: {replace: url => locations.push(url)}};
  const window = {open: (url, target) => {
    assert.equal(url, 'about:blank'); assert.equal(target, '_blank');
    return blocked ? null : popup;
  }};
  const context = {window, document: {querySelectorAll: () => [panel]},
    navigator: {clipboard: {writeText: value => { copied.push(value); return Promise.resolve(); }}},
    WorkspacePage: {run: callback => callback()}};
  vm.runInNewContext(fs.readFileSync('static/js/prpwd-review.js', 'utf8'), context);
  assert(buttons.every(button => button.disabled));
  events.open();
  await Promise.resolve();
  if (blocked) {
    assert.equal(opened.value, '');
    assert.match(feedback.textContent, /blocked/);
    assert(buttons.every(button => button.disabled));
    assert.equal(locations.length, 0);
  } else {
    assert.equal(opened.value, number.value);
    assert.deepEqual(copied, [number.value]);
    assert.deepEqual(locations, ['https://registry.example.test/manual']);
    assert.equal(popup.opener, null);
    assert.equal(meta[0].content, 'no-referrer');
    assert(buttons.every(button => !button.disabled));
    number.value = '00-0000-000-0000002'; events.input();
    assert.equal(opened.value, '');
    assert(buttons.every(button => button.disabled));
  }
}
(async () => { await check(); await check(true); console.log('PRPWD popup, clipboard, privacy and changed-number checks passed.'); })()
  .catch(error => { console.error(error); process.exitCode = 1; });
