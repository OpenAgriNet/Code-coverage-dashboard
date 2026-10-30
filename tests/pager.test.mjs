// Run with: node --test tests/pager.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import P from '../assets/pager.js';

test('page numbers keep the first, the last and two either side of the current one', () => {
  assert.deepEqual(P.pages(1, 1), [1]);
  assert.deepEqual(P.pages(1, 5), [1, 2, 3, null, 5]);
  assert.deepEqual(P.pages(6, 10), [1, null, 4, 5, 6, 7, 8, null, 10]);
  assert.deepEqual(P.pages(10, 10), [1, null, 8, 9, 10]);
});
