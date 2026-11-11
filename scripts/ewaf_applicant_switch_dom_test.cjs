// Synthetic DOM boundary test: no browser, real applicants or network access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {performance} = require('node:perf_hooks');

const listeners = new Map(), requests = [], navigations = [];
const location = {href: 'http://example.test/ewaf/programs/synthetic/', assign: url => navigations.push(String(url))};
const history = {
  pushState(_, __, url) { location.href = String(url); },
  replaceState(_, __, url) { location.href = String(url); },
};
const nodes = new Map();
const panel = id => ({dataset: {application: id},
  cloneNode() { return panel(id); },
  replaceWith(next) { nodes.set('readiness', next); },
  setAttribute() {}, removeAttribute() {},
  focus() { this.focused = true; }, scrollIntoView() { this.revealed = true; }});
const templates = ['a', 'b', 'c'].map(id => ({dataset: {applicantPanel: id}, content: {firstElementChild: panel(id)}}));
const panels = {dataset: {run: '7', defaultApplicant: 'a'}, querySelectorAll: () => templates};
const rows = ['a', 'b', 'c'].map(id => {
  const link = {href: `http://example.test/ewaf/programs/synthetic/?run=7&review=${id}#readiness`,
    attributes: {}, setAttribute(key, value) { this.attributes[key] = value; },
    removeAttribute(key) { delete this.attributes[key]; }};
  const row = {dataset: {applicant: id}, querySelector: () => link};
  row.classList = {toggle(_, selected) { row.selected = selected; }};
  return row;
});
nodes.set('readiness', panel('a'));
nodes.set('applicant-panels', panels);
nodes.set('ranking-filter-status', {});
const document = {
  documentElement: {classList: {add() {}}},
  getElementById: id => nodes.get(id) || null,
  querySelector: selector => selector === '.ewaf-page' ? {} : nodes.get(selector.slice(1)) || null,
  querySelectorAll: selector => selector === 'tr[data-applicant]' ? rows : [],
};
const window = {};
const on = (target, name, callback) => listeners.set(`${target === window ? 'window' : 'document'}:${name}`, callback);
let parsedDocument = {getElementById: () => null};
vm.runInNewContext(fs.readFileSync('static/js/ewaf-workspace.js', 'utf8'), {
  document, window, location, history, URL, URLSearchParams, AbortController, clearTimeout,
  matchMedia: () => ({matches: false}),
  DOMParser: class { parseFromString() { return parsedDocument; } },
  WorkspacePage: {run: callback => callback({on, setTimeout,
    fetch: (url, options) => new Promise(resolve => requests.push({url, options, resolve}))})},
});

function click(id, {href, blankRow = false, ctrlKey = false} = {}) {
  const row = rows.find(item => item.dataset.applicant === id);
  const link = href ? {...row.querySelector(), href} : row.querySelector();
  const event = {button: 0, ctrlKey, prevented: false, preventDefault() { this.prevented = true; },
    target: {closest: selector => selector === '[data-applicant-open]' ? (blankRow ? null : link) :
      selector === 'tr[data-applicant]' ? row : null}};
  listeners.get('document:click')(event);
  return event;
}
const flush = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  const start = performance.now();
  for (let i = 0; i < 100; i++) click(i % 2 ? 'b' : 'a', {blankRow: i % 3 === 0});
  const elapsed = performance.now() - start;
  assert.equal(requests.length, 0, 'Loaded row clicks must never fetch the whole workspace.');
  assert.equal(nodes.get('readiness').dataset.application, 'b');
  assert.equal(nodes.get('readiness').focused, true);
  assert.equal(rows.find(row => row.selected).dataset.applicant, 'b');
  assert.equal(rows[1].querySelector().attributes['aria-current'], 'true');
  assert.equal(rows[0].querySelector().attributes['aria-current'], undefined);
  assert.equal(new URL(location.href).searchParams.get('review'), 'b');

  // Back to the initial URL restores its first applicant locally.
  location.href = 'http://example.test/ewaf/programs/synthetic/';
  listeners.get('window:popstate')();
  assert.equal(nodes.get('readiness').dataset.application, 'a');
  assert.equal(requests.length, 0);
  assert.equal(click('b', {ctrlKey: true}).prevented, false);

  // A different ranking cannot reuse cards from the one currently loaded.
  click('c', {href: 'http://example.test/ewaf/programs/synthetic/?run=99&review=c'});
  assert.equal(requests.length, 1);
  click('b');
  assert.equal(requests[0].options.signal.aborted, true);
  requests[0].resolve({ok: true, text: async () => '<stale-response>'});
  await flush();
  assert.equal(nodes.get('readiness').dataset.application, 'b');
  assert.equal(navigations.length, 0, 'An obsolete response must not navigate away from the chosen row.');

  // An uncached/filter navigation still uses the protected server route.
  const filtered = 'http://example.test/ewaf/programs/synthetic/?q=new&run=7&review=c';
  click('c', {href: filtered});
  assert.equal(requests.length, 2);
  assert.equal(requests[1].options.credentials, 'same-origin');
  assert.equal(requests[1].options.cache, 'no-store');
  requests[1].resolve({ok: false, text: async () => '<login-or-permission-response>'});
  await flush();
  assert.deepEqual(navigations, [filtered]);
  console.log(`PASS: 100 local switches in ${elapsed.toFixed(2)} ms with zero fetches; matching inputs/highlights/history, row clicks, modifier keys, cutoff between rankings, stale-response cancellation and protected fallback.`);
})().catch(error => { console.error(error); process.exitCode = 1; });
