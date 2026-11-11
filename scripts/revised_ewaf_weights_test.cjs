// Native Node checks plus a small DOM harness for independent draft controls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/ewaf-revised-weights.js', 'utf8');
const {remainder} = require('../static/js/ewaf-revised-weights.js');
assert.equal(remainder([3421, 2360, 1774, 1223]).hm, 1222);
assert.equal(remainder([6255, 1948, 1407, 1223]).valid, false);
assert.equal(remainder([6255, 1948, 1407, 1223]).hm, -833);
assert.equal(remainder([5422, 1948, 1407, 1223]).hm, 0);
function control(value) {
    return {value, handlers: {}, addEventListener(event, fn) { this.handlers[event] = fn; },
        setCustomValidity(value) { this.error = value; }, classList: {toggle() {}}};
}
const numbers = [3421, 2360, 1774, 1223].map(v => control((v / 100).toFixed(2)));
const ranges = numbers.map(n => control(n.value));
const mode = control('DOCUMENT_EXAMPLE'), feedback = control(''), reset = control(''), hm = control(''), total = control('');
const buttons = [{}, {}], codes = ['HI', 'SI', 'ES', 'PA'];
const form = {querySelector(selector) {
    const i = codes.findIndex(c => selector.includes('"' + c + '"'));
    return selector.includes('number') ? numbers[i] : ranges[i];
}, querySelectorAll() { return buttons; }};
const pageDocument = {getElementById(id) {
    return {'revised-weight-form': form, id_mode: mode, 'weight-feedback': feedback,
        'reset-example': reset, 'hm-weight': hm, 'total-weight': total}[id];
}};
vm.runInNewContext(source, {document: pageDocument});
assert.equal(hm.textContent, '12.22');
assert.equal(ranges[0].max, '46.43');
numbers[0].value = '40.00'; numbers[0].handlers.input();
assert.deepEqual(numbers.map(v => v.value), ['40.00', '23.60', '17.74', '12.23']);
assert.equal(hm.textContent, '6.43');
assert.equal(mode.value, 'DRAFT_SENSITIVITY');
numbers[0].value = '62.55'; numbers[0].handlers.input();
assert.equal(numbers[0].value, '62.55');
assert.equal(total.textContent, 'Invalid');
assert.ok(buttons.every(b => b.disabled));
reset.handlers.click();
assert.deepEqual(numbers.map(v => v.value), ['34.21', '23.60', '17.74', '12.23']);
assert.equal(hm.textContent, '12.22');
assert.equal(mode.value, 'DOCUMENT_EXAMPLE');
assert.ok(buttons.every(b => !b.disabled));
console.log('PASS: exact remainder, infeasible maximum, zero exploration, effective range, independent controls, immediate HM, invalid-input preservation, submit blocking, defaults.');
