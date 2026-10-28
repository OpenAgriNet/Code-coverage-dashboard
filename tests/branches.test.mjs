// Run with: node --test tests/*.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import B from '../assets/branches.js';

const dev = [
  { repository: 'network-adapter', branch: 'development', branch_source: 'pattern' },
  { repository: 'knowledge-provider', branch: 'main', branch_source: 'default' },
  { repository: 'decision-support-system', branch: 'main', branch_source: 'default' },
  { repository: 'helmcharts', branch: 'dev', branch_source: 'config' },
];
const main = dev.map(r => ({ ...r, branch: 'main', branch_source: 'default' }));

test('Development keeps only repositories whose development branch was found', () => {
  assert.deepEqual(B.devOnly(dev).map(r => r.repository), ['network-adapter', 'helmcharts']);
  assert.deepEqual(B.devOnly(undefined), []);
});

test('the note names the repositories left out of Development, sorted', () => {
  const n = B.note('dev', dev, main);
  assert.deepEqual(n.hidden, ['decision-support-system', 'knowledge-provider']);
  assert.match(n.text, /2 repositories have no development branch, so they are shown only under Main/);
  assert.match(B.note('dev', dev.slice(0, 2), main).text, /1 repository has no development branch, so it is shown only under Main/);
});

test('Main hides nothing and says how many it shows', () => {
  assert.deepEqual(B.note('main', dev, main), { text: "Each repository's default branch (4).", hidden: [] });
});

test('with every development branch found there is nothing to explain', () => {
  assert.deepEqual(B.note('dev', [dev[0]], main).hidden, []);
});
