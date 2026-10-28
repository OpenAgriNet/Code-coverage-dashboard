// Run with: node --test tests/filters.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import F from '../assets/filters.js';

const items = [
  { repo: 'a', tags: ['DPG'], sec: 'Passing', langs: ['Go', 'YAML'] },
  { repo: 'b', tags: ['DPG', 'core'], sec: 'Failing', langs: ['Python'] },
  { repo: 'c', tags: [], sec: 'Failing', langs: ['Go'] },
  { repo: 'd', tags: ['core'], sec: 'Passing', langs: ['Python', 'JS'] },
];
const facets = [
  { key: 'tag', label: 'Tag', get: i => i.tags },
  { key: 'sec', label: 'Security', get: i => i.sec, order: ['Passing', 'Failing'] },
  { key: 'lang', label: 'Language', get: i => i.langs },
];
const names = list => list.map(i => i.repo);

test('no selection shows everything', () => {
  assert.deepEqual(names(F.filterItems(items, facets, {})), ['a', 'b', 'c', 'd']);
  assert.deepEqual(names(F.filterItems(items, facets, { tag: [] })), ['a', 'b', 'c', 'd']);
});

test('values inside one filter are OR-ed', () => {
  assert.deepEqual(names(F.filterItems(items, facets, { sec: ['Passing', 'Failing'] })), ['a', 'b', 'c', 'd']);
  assert.deepEqual(names(F.filterItems(items, facets, { tag: ['DPG', 'core'] })), ['a', 'b', 'd']);
});

test('different filters are AND-ed', () => {
  assert.deepEqual(names(F.filterItems(items, facets, { tag: ['DPG'], sec: ['Failing'] })), ['b']);
  assert.deepEqual(names(F.filterItems(items, facets, { tag: ['DPG', 'core'], sec: ['Failing'], lang: ['Go'] })), []);
});

test('multi-valued items match when any value is selected', () => {
  assert.deepEqual(names(F.filterItems(items, facets, { lang: ['JS'] })), ['d']);
  assert.deepEqual(names(F.filterItems(items, facets, { lang: ['Go'] })), ['a', 'c']);
});

test('text search combines with filters', () => {
  const textOf = i => i.repo;
  assert.deepEqual(names(F.filterItems(items, facets, { sec: ['Failing'] }, 'B', textOf)), ['b']);
  assert.deepEqual(names(F.filterItems(items, facets, {}, 'zzz', textOf)), []);
});

test('option counts ignore the facet itself but respect the others', () => {
  const sel = { tag: ['DPG'], sec: ['Failing'] };
  const sec = F.optionList(items, facets[1], facets, sel);
  assert.deepEqual(sec.map(o => [o.value, o.count, o.selected]), [['Passing', 1, false], ['Failing', 1, true]]);  // DPG repos: a passing, b failing
  const tag = F.optionList(items, facets[0], facets, sel);
  assert.deepEqual(Object.fromEntries(tag.map(o => [o.value, o.count])), { DPG: 1, core: 1 });  // failing repos: b (DPG, core), c
});

test('an option that would empty the result has count 0', () => {
  const lang = F.optionList(items, facets[2], facets, { tag: ['DPG'], sec: ['Passing'] });
  assert.deepEqual(Object.fromEntries(lang.map(o => [o.value, o.count])), { Go: 1, YAML: 1, Python: 0, JS: 0 });
});

test('a selected value missing from the data stays listed with count 0', () => {
  const tag = F.optionList(items, facets[0], facets, { tag: ['gone'] });
  assert.deepEqual(tag.find(o => o.value === 'gone'), { value: 'gone', label: 'gone', count: 0, selected: true });
});

test('options follow the given order, then alphabetical', () => {
  assert.deepEqual(F.optionList(items, facets[1], facets, {}).map(o => o.value), ['Passing', 'Failing']);
  assert.deepEqual(F.optionList(items, facets[2], facets, {}).map(o => o.value), ['Go', 'JS', 'Python', 'YAML']);
});

test('option counts respect the text search', () => {
  const textOf = i => i.repo;
  const sec = F.optionList(items, facets[1], facets, {}, 'a', textOf);
  assert.deepEqual(Object.fromEntries(sec.map(o => [o.value, o.count])), { Passing: 1, Failing: 0 });
});

test('url parameters round-trip and repeat per value', () => {
  const sel = { tag: ['DPG', 'core'], sec: ['Failing'] };
  const q = F.writeParams('', facets, 'q', sel, 'net');
  assert.equal(q, 'tag=DPG&tag=core&sec=Failing&q=net');
  assert.deepEqual(F.readParams('?' + q, facets, 'q'), { selected: sel, text: 'net' });
});

test('values with spaces, commas and ampersands survive the url', () => {
  const sel = { sec: ['A, B & C'] };
  assert.deepEqual(F.readParams('?' + F.writeParams('', facets, null, sel, ''), facets, null).selected, sel);
});

test('writing parameters keeps unrelated ones and drops cleared ones', () => {
  assert.equal(F.writeParams('?view=main&tag=old&q=old', facets, 'q', { sec: ['Failing'] }, ''), 'view=main&sec=Failing');
});

test('a facet can use its own url parameter name', () => {
  const f = [{ key: 'repository', param: 'repo', label: 'Repository', get: i => i.repo }];
  assert.equal(F.writeParams('', f, null, { repository: ['a', 'b'] }, ''), 'repo=a&repo=b');
  assert.deepEqual(F.readParams('?repo=a&repo=a&repo=b', f, null).selected, { repository: ['a', 'b'] });
});
