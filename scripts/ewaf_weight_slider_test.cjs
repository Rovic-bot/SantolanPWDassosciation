const assert = require('assert/strict');
const {valid, cascade, reorder, begin} = require('../static/js/ewaf-weights.js');
let proposal = {order: ['SI', 'ES', 'PA', 'ND'], weights: {SI: 4000, ES: 3000, PA: 2000, ND: 1000}};
proposal = cascade(proposal, 0, 5000);
assert.deepEqual(proposal.weights, {SI: 5000, ES: 2500, PA: 1667, ND: 833});
proposal = cascade(proposal, 1, 3000);
assert.deepEqual(proposal.weights, {SI: 5000, ES: 3000, PA: 1334, ND: 666});
proposal = cascade(proposal, 2, 1400);
assert.deepEqual(proposal.weights, {SI: 5000, ES: 3000, PA: 1400, ND: 600});
assert.equal(cascade(proposal, 2, 10000).weights.ND, 556);
const moved = reorder(proposal, 3, -1);
assert.deepEqual(moved.order, ['SI', 'ES', 'ND', 'PA']);
assert.equal(moved.weights.ND, 1400);
let seed = 142;
for (let i = 0; i < 500; i++) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    const index = i % 3;
    const before = structuredClone(proposal);
    proposal = cascade(proposal, index, seed % 12000 - 1000);
    assert.ok(valid(proposal));
    for (const code of before.order.slice(0, index)) assert.equal(proposal.weights[code], before.weights[code]);
    if (i % 5 === 0) proposal = reorder(proposal, i % 4, i % 4 === 3 ? -1 : 1);
    assert.ok(valid(proposal));
}
const household = {order: ['HI', 'SI', 'ES', 'PA', 'HM'],
    weights: {HI: 3421, SI: 2360, ES: 1774, PA: 1223, HM: 1222}};
let current = structuredClone(household);
for (const [index, target] of [[0, 4000], [1, 2500], [2, 1800], [3, 1200]]) {
    const before = structuredClone(current);
    current = cascade(current, index, target);
    assert.ok(valid(current));
    assert.equal(current.weights[current.order[index]], target);
    for (const code of before.order.slice(0, index)) assert.equal(current.weights[code], before.weights[code]);
    for (const code of before.order.slice(index + 1)) assert.ok(current.weights[code] < before.weights[code]);
}
assert.deepEqual(cascade(current, 4, 10000), current, 'last criterion receives the remainder');
for (const code of household.order) {
    let ordered = structuredClone(household);
    while (ordered.order[0] !== code) ordered = reorder(ordered, ordered.order.indexOf(code), -1);
    const increased = cascade(ordered, 0, 10000);
    assert.ok(increased.weights[code] > ordered.weights[code], code + ' can become highest priority');
    assert.ok(increased.weights[code] < 10000, '100% drag stays within positive Saaty weights');
    assert.ok(valid(increased));
}
for (let i = 0; i < 1000; i++) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    const index = i % 4, before = structuredClone(current);
    current = cascade(current, index, seed % 12000 - 1000);
    assert.ok(valid(current));
    for (const code of before.order.slice(0, index)) assert.equal(current.weights[code], before.weights[code]);
    const delta = current.weights[current.order[index]] - before.weights[before.order[index]];
    for (const code of before.order.slice(index + 1)) {
        if (delta > 0) assert.ok(current.weights[code] <= before.weights[code]);
        if (delta < 0) assert.ok(current.weights[code] >= before.weights[code]);
    }
    if (i % 5 === 0) current = reorder(current, i % 5, i % 5 === 4 ? -1 : 1);
    assert.ok(valid(current));
}
assert.deepEqual(household.weights, {HI: 3421, SI: 2360, ES: 1774, PA: 1223, HM: 1222});
let ses = {order: ['SES', 'ES', 'PA', 'HM'], weights: {SES: 4478, ES: 2322, PA: 1601, HM: 1599}};
// Independently calculated examples: both directions, with only later rows changing.
const chosen = {order: ['SES', 'ES', 'PA', 'HM'], weights: {SES: 5000, ES: 2500, PA: 1500, HM: 1000}};
let started = begin(chosen.order, 5000);
assert.deepEqual(started.weights, {SES: 5000, ES: 1667, PA: 1667, HM: 1666});
started = cascade(started, 1, 2500);
started = cascade(started, 2, 1500);
assert.deepEqual(started, chosen, 'three slider gestures set the four proposed weights without typed percentages');
for (const code of chosen.order) {
    const order = [code, ...chosen.order.filter(item => item !== code)];
    for (const target of [0, 1, 2500, 4000, 5000, 8000, 10000]) {
        const start = begin(order, target);
        assert.ok(valid(start));
        assert.equal(start.order[0], code);
    }
}
for (const [index, value, expected] of [
    [0, 6000, {SES: 6000, ES: 2000, PA: 1200, HM: 800}],
    [0, 4500, {SES: 4500, ES: 2750, PA: 1650, HM: 1100}],
    [1, 2800, {SES: 5000, ES: 2800, PA: 1320, HM: 880}],
    [1, 2200, {SES: 5000, ES: 2200, PA: 1680, HM: 1120}],
    [2, 1700, {SES: 5000, ES: 2500, PA: 1700, HM: 800}],
    [2, 1250, {SES: 5000, ES: 2500, PA: 1250, HM: 1250}],
]) {
    const updated = cascade(chosen, index, value);
    assert.deepEqual(updated.weights, expected);
    assert.equal(Object.values(updated.weights).reduce((sum, weight) => sum + weight, 0), 10000);
}
for (const code of ses.order) {
    let moved = structuredClone(ses);
    while (moved.order[0] !== code) moved = reorder(moved, moved.order.indexOf(code), -1);
    const after = cascade(moved, 0, 10000);
    assert.ok(valid(after));
    assert.ok(after.weights[code] > moved.weights[code]);
    assert.ok(after.weights[code] < 10000);
    assert.equal(after.order[0], code);
}
for (let i = 0; i < 1000; i++) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    const index = i % 3, before = structuredClone(ses);
    ses = cascade(ses, index, seed % 12000 - 1000);
    assert.ok(valid(ses));
    assert.equal(Object.values(ses.weights).reduce((sum, value) => sum + value, 0), 10000);
    for (const code of before.order.slice(0, index)) assert.equal(ses.weights[code], before.weights[code]);
    assert.deepEqual(Object.keys(ses.weights).sort(), ['ES', 'HM', 'PA', 'SES']);
    if (i % 5 === 0) ses = reorder(ses, i % 4, i % 4 === 3 ? -1 : 1);
    assert.ok(valid(ses));
}
console.log('2,500 cascade/reorder cases and six exact SES cascade examples passed: total 100%, fixed earlier weights, code association and Saaty limits.');
