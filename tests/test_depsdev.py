import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.lookups import depsdev as d

def fake_fetch(responses):
    return lambda path: responses.get(path)

PKG = {'versions': [{'versionKey': {'version': '0.141.1'}, 'isDefault': False}, {'versionKey': {'version': '0.162.0'}, 'isDefault': True}]}

def test_dep_info_uses_pinned_version_license():
    got = d.dep_info('python', 'fastapi', '0.141.1', fake_fetch({
        'PYPI/packages/fastapi': PKG, 'PYPI/packages/fastapi/versions/0.141.1': {'licenses': ['MIT']}}))
    assert got == {'ecosystem': 'python', 'name': 'fastapi', 'version': '0.141.1', 'latest': '0.162.0', 'license': 'MIT', 'license_of': 'pinned'}

def test_dep_info_falls_back_to_latest_when_pinned_version_unknown():
    got = d.dep_info('python', 'fastapi', '>=99', fake_fetch({
        'PYPI/packages/fastapi': PKG, 'PYPI/packages/fastapi/versions/0.162.0': {'licenses': ['MIT', 'Apache-2.0']}}))
    assert got['license'] == 'MIT, Apache-2.0' and got['license_of'] == 'latest'

def test_dep_info_quotes_scoped_npm_names_and_prefixes_go_versions():
    seen = []
    def fetch(path):
        seen.append(path)
        return None
    d.dep_info('npm', '@radix-ui/react-avatar', '^1.2.6', fetch)
    assert seen == ['NPM/packages/%40radix-ui%2Freact-avatar']
    got = d.dep_info('golang', 'github.com/a/b', '1.2.0', fake_fetch({
        'GO/packages/github.com%2Fa%2Fb': {'versions': []}, 'GO/packages/github.com%2Fa%2Fb/versions/v1.2.0': {'licenses': ['BSD-3-Clause']}}))
    assert got['license'] == 'BSD-3-Clause'

def test_dep_info_skips_docker_and_actions():
    got = d.dep_info('docker', 'redis', 'alpine', lambda p: (_ for _ in ()).throw(AssertionError('no lookup')))
    assert got['license'] is None and got['license_of'] is None

def test_lookup_failure_is_marked_error_not_unknown():
    def boom(path):
        raise RuntimeError('429')
    got = d.dep_info('python', 'fastapi', '0.1', boom)
    assert got['license'] is None and got['license_of'] == 'error'

def test_dep_info_records_the_source_repository():
    def fetch(path):
        if path.endswith('/versions/18.3.1'):
            return {'licenses': ['MIT'], 'relatedProjects': [{'projectKey': {'id': 'github.com/facebook/react'}, 'relationType': 'ISSUE_TRACKER'},
                                                          {'projectKey': {'id': 'github.com/facebook/react'}, 'relationType': 'SOURCE_REPO'}]}
        return {'versions': [{'versionKey': {'version': '18.3.1'}, 'isDefault': True}]}
    assert d.dep_info('npm', 'react', '18.3.1', fetch=fetch)['project'] == 'github.com/facebook/react'
