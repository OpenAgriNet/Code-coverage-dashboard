import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from stackinfo.lookups import osv as v

def vuln(vid, name='jinja2', eco='PyPI', fixed=(), severity='HIGH', aliases=(), summary='s', rtype='ECOSYSTEM', **kw):
    events = [{'introduced': '0'}] + [{'fixed': f} for f in fixed]
    return {'id': vid, 'aliases': list(aliases), 'summary': summary, 'database_specific': {'severity': severity},
            'affected': [{'package': {'name': name, 'ecosystem': eco}, 'ranges': [{'type': rtype, 'events': events}]}], **kw}

def dep(name='jinja2', version='3.1.0', eco='python'):
    return {'ecosystem': eco, 'name': name, 'version': version}

def run(deps, db, ids):
    """db: vuln id -> record; ids: list of ids OSV reports for every queried package."""
    v.DETAILS.clear()
    post = lambda path, body: {'results': [{'vulns': [{'id': i} for i in ids]} for _ in body['queries']]}
    v.annotate(deps, post=post, fetch=lambda path: db[path.rsplit('/', 1)[1]], log=lambda m: None)
    return deps

def test_fixed_version_is_the_lowest_fix_above_the_current_version():
    x = vuln('A', fixed=['2.0.1', '3.1.4', '3.0.2'])
    assert v.fixed_version(x, 'PyPI', 'jinja2', '3.1.0') == '3.1.4'
    assert v.fixed_version(x, 'PyPI', 'jinja2', '2.0.0') == '2.0.1'
    assert v.fixed_version(x, 'PyPI', 'jinja2', '3.1.4') is None

def test_fixed_version_none_when_never_fixed_and_ignores_commit_ranges_and_other_packages():
    assert v.fixed_version(vuln('A'), 'PyPI', 'jinja2', '3.1.0') is None
    assert v.fixed_version(vuln('A', fixed=['deadbeef'], rtype='GIT'), 'PyPI', 'jinja2', '3.1.0') is None
    assert v.fixed_version(vuln('A', name='other', fixed=['9.9.9']), 'PyPI', 'jinja2', '3.1.0') is None

def test_package_names_compare_the_way_pypi_does():
    assert v.fixed_version(vuln('A', name='Pillow', fixed=['10.0.1']), 'PyPI', 'pillow', '10.0.0') == '10.0.1'
    assert v.fixed_version(vuln('A', name='typing_extensions', fixed=['4.0']), 'PyPI', 'typing-extensions', '3.0') == '4.0'

def test_numeric_not_text_comparison_and_go_v_prefix():
    assert v.fixed_version(vuln('A', name='golang.org/x/crypto', eco='Go', fixed=['0.9.0', '0.31.0']), 'Go', 'golang.org/x/crypto', 'v0.10.0') == '0.31.0'

def test_annotate_summarises_items_fixed_in_and_severity():
    db = {'GHSA-1': vuln('GHSA-1', fixed=['3.1.3'], severity='MODERATE', aliases=['CVE-1']), 'GHSA-2': vuln('GHSA-2', fixed=['3.1.5'], severity='CRITICAL'),
          'GHSA-3': vuln('GHSA-3', severity='LOW')}
    d = run([dep()], db, ['GHSA-1', 'GHSA-2', 'GHSA-3'])[0]['vulns']
    assert d['count'] == 3 and d['severity'] == 'CRITICAL' and d['fixed_in'] == '3.1.5' and d['unfixed'] == 1
    assert d['by_severity'] == {'CRITICAL': 1, 'MODERATE': 1, 'LOW': 1}
    assert d['checked_version'] == '3.1.0' and d['exact'] is True
    assert [i['id'] for i in d['items']] == ['GHSA-1', 'GHSA-2', 'GHSA-3'] and d['items'][0]['cve'] == 'CVE-1'
    assert d['items'][0]['url'] == 'https://osv.dev/vulnerability/GHSA-1'

def test_same_advisory_under_two_ids_counts_once_and_withdrawn_is_dropped():
    db = {'GHSA-1': vuln('GHSA-1', fixed=['3.1.3'], aliases=['CVE-1', 'PYSEC-1']), 'PYSEC-1': vuln('PYSEC-1', fixed=['3.1.3'], aliases=['CVE-1']),
          'GHSA-9': vuln('GHSA-9', fixed=['3.1.3'], withdrawn='2026-01-01')}
    assert run([dep()], db, ['GHSA-1', 'PYSEC-1', 'GHSA-9'])[0]['vulns']['count'] == 1

def test_no_vulnerabilities_is_zero_not_unchecked():
    d = run([dep()], {}, [])[0]['vulns']
    assert d['count'] == 0 and d['severity'] is None and d['fixed_in'] is None and d['items'] == []

def test_not_checked_when_unsupported_or_version_unknown():
    deps = run([dep('redis', 'alpine', 'docker'), dep('actions/checkout', 'v4', 'githubAction'), dep('x', 'latest'), dep('y', '${V}')], {}, [])
    assert [d['vulns'] for d in deps] == [None, None, None, None]

def test_range_is_checked_at_its_lowest_version_and_marked_not_exact():
    d = run([dep('vite', '^5.0.0', 'npm')], {'G': vuln('G', name='vite', eco='npm', fixed=['5.4.9'])}, ['G'])[0]['vulns']
    assert d['checked_version'] == '5.0.0' and d['exact'] is False and d['fixed_in'] == '5.4.9'

def test_lookup_failure_leaves_unchecked_and_does_not_raise():
    logs = []
    def boom(path, body):
        raise RuntimeError('503')
    deps = [dep()]
    v.annotate(deps, post=boom, fetch=None, log=logs.append)
    assert deps[0]['vulns'] is None and any('OSV lookup failed' in l for l in logs)

def test_details_are_fetched_once_per_advisory_across_packages():
    fetched = []
    v.DETAILS.clear()
    post = lambda path, body: {'results': [{'vulns': [{'id': 'G'}]} for _ in body['queries']]}
    def fetch(path):
        fetched.append(path)
        return vuln('G', fixed=['9.0'])
    v.annotate([dep('a'), dep('b')], post=post, fetch=fetch, log=lambda m: None)
    assert fetched == ['/vulns/G']

def test_unknown_severity_and_medium_alias():
    assert v.severity({}) == 'UNKNOWN' and v.severity({'database_specific': {'severity': 'MEDIUM'}}) == 'MODERATE'

def test_prerelease_is_older_than_its_final_release():
    assert v.vkey('2.0.0-rc.1') < v.vkey('2.0.0') and v.vkey('5.0.0rc1') < v.vkey('5.0.0') and v.vkey('1.2') == v.vkey('1.2.0')
    assert v.vkey('0.0.10') > v.vkey('0.0.9')
    x = vuln('A', fixed=['2.0.0'])
    assert v.fixed_version(x, 'PyPI', 'jinja2', '2.0.0rc1') == '2.0.0'  # was shown as "no fix released"

@pytest.mark.parametrize('declared,exact', [('1.2.3', True), ('v1.2.3', True), ('==1.2.3', True), ('=1.2.3', True), ('^1.2.3', False), ('>=1.2', False), ('1.x', False), ('~1.2.3', False), ('latest', False)])
def test_is_exact(declared, exact):
    assert v.is_exact(declared) is exact

def test_one_failing_advisory_lookup_leaves_only_that_dependency_unchecked():
    v.DETAILS.clear()
    def post(path, body):
        return {'results': [{'vulns': [{'id': 'BAD' if q['package']['name'] == 'a' else 'OK'}]} for q in body['queries']]}
    def fetch(path):
        if path.endswith('BAD'):
            raise RuntimeError('429')
        return vuln('OK', fixed=['9.0'])
    deps = [dep('a'), dep('b')]
    logs = []
    v.annotate(deps, post=post, fetch=fetch, log=logs.append)
    assert deps[0]['vulns'] is None and deps[1]['vulns']['count'] == 1 and any('a:' in l for l in logs)

def test_installed_version_from_the_lockfile_is_checked_instead_of_the_range():
    deps = [{'ecosystem': 'npm', 'name': 'vite', 'version': '^5.0.0', 'installed': '5.4.2'}]
    asked = []
    def post(path, body):
        asked.extend(q['version'] for q in body['queries'])
        return {'results': [{}]}
    v.annotate(deps, post=post, fetch=lambda p: {})
    assert asked == ['5.4.2'] and deps[0]['vulns']['checked_version'] == '5.4.2' and deps[0]['vulns']['exact'] is True
