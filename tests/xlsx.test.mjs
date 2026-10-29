// Run with: node --test tests/*.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import X from '../assets/xlsx.js';
import E from '../assets/export.js';

const text = b => new TextDecoder().decode(b);

test('a workbook is a zip with one worksheet per sheet, header bold and frozen', () => {
  const out = X.build([{ name: 'Coverage', rows: [['Repository', 'Coverage %'], ['a & b', 96.5]] }, { name: 'Empty', rows: [['Only a header']] }]);
  assert.deepEqual([...out.slice(0, 4)], [0x50, 0x4b, 0x03, 0x04]);
  const s = text(out);
  assert.match(s, /xl\/worksheets\/sheet2\.xml/);
  assert.match(s, /<c r="A2" t="inlineStr"><is><t xml:space="preserve">a &amp; b<\/t><\/is><\/c><c r="B2"><v>96.5<\/v><\/c>/);
  assert.match(s, /<c r="A1" t="inlineStr" s="1">/);
  assert.match(s, /state="frozen"/);
  assert.match(s, /<autoFilter ref="A1:B2"\/>/);
});

test('sheet names are cut to 31 characters, cleaned and unique', () => {
  assert.deepEqual(X.names([{ name: 'Vulnerabilities (development) and more' }, { name: 'a/b' }, { name: 'A/B' }]),
    ['Vulnerabilities (development) a', 'a b', 'A B~2']);
});

test('dependencies and vulnerabilities become one row per package and per advisory', () => {
  const deps = [{ repository: 'r', name: 'redis', ecosystem: 'docker', kind: 'Cache', version: '7', license: 'MIT', license_class: 'green', stars: 5,
    vulns: { count: 1, severity: 'HIGH', checked_version: '7', items: [{ id: 'GHSA-1', cve: 'CVE-1', severity: 'HIGH', fixed: '1.2', summary: 'glibc 2.36: bad', url: 'u' }] } }];
  const d = E.dependencies(deps, { green: 'Preferred' });
  assert.deepEqual(d[1].slice(0, 4), ['r', 'redis', 'redis', 'Cache']);
  assert.equal(d[1][11], 'Preferred (green)');
  assert.deepEqual(E.vulnerabilities(deps)[1], ['r', 'redis', '7', 'glibc', '2.36', 'CVE-1', 'GHSA-1', 'high', '1.2', 'bad', 'u']);
});
