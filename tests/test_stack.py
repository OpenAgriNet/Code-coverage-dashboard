import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import collect_stack as s

def test_summarize_sorts_languages_and_dedupes_dependencies():
    raw = {'languages': {'YAML': 5, 'Go': 30, 'Markdown': 5}, 'techs': ['redis', 'golang', 'redis'],
           'dependencies': [['golang', 'github.com/b/x', 'v1.0.0'], ['docker', 'redis', 'alpine'], ['golang', 'github.com/b/x', 'v1.0.0']]}
    got = s.summarize(raw)
    assert got['languages'] == [('Go', 30), ('Markdown', 5), ('YAML', 5)]
    assert got['techs'] == ['golang', 'redis']
    assert got['dependencies'] == [['docker', 'redis', 'alpine'], ['golang', 'github.com/b/x', 'v1.0.0']]

def test_clean_version():
    assert s.clean_version('^1.2.6') == '1.2.6'
    assert s.clean_version('>=2.0,<3') == '2.0'
    assert s.clean_version('v1.6.0') == 'v1.6.0'
    assert s.clean_version('latest') is None
    assert s.clean_version('${REGISTRY_IMAGE_TAG}') is None

def fake_fetch(responses):
    return lambda path: responses.get(path)

PKG = {'versions': [{'versionKey': {'version': '0.141.1'}, 'isDefault': False}, {'versionKey': {'version': '0.162.0'}, 'isDefault': True}]}

def test_dep_info_uses_pinned_version_license():
    got = s.dep_info('python', 'fastapi', '0.141.1', fake_fetch({
        'PYPI/packages/fastapi': PKG, 'PYPI/packages/fastapi/versions/0.141.1': {'licenses': ['MIT']}}))
    assert got == {'ecosystem': 'python', 'name': 'fastapi', 'version': '0.141.1', 'latest': '0.162.0', 'license': 'MIT', 'license_of': 'pinned'}

def test_dep_info_falls_back_to_latest_when_pinned_version_unknown():
    got = s.dep_info('python', 'fastapi', '>=99', fake_fetch({
        'PYPI/packages/fastapi': PKG, 'PYPI/packages/fastapi/versions/0.162.0': {'licenses': ['MIT', 'Apache-2.0']}}))
    assert got['license'] == 'MIT OR Apache-2.0' and got['license_of'] == 'latest'

def test_dep_info_quotes_scoped_npm_names_and_prefixes_go_versions():
    seen = []
    def fetch(path):
        seen.append(path)
        return None
    s.dep_info('npm', '@radix-ui/react-avatar', '^1.2.6', fetch)
    assert seen == ['NPM/packages/%40radix-ui%2Freact-avatar']
    got = s.dep_info('golang', 'github.com/a/b', '1.2.0', fake_fetch({
        'GO/packages/github.com%2Fa%2Fb': {'versions': []}, 'GO/packages/github.com%2Fa%2Fb/versions/v1.2.0': {'licenses': ['BSD-3-Clause']}}))
    assert got['license'] == 'BSD-3-Clause'

def v(version, published, default=False):
    return {'versionKey': {'version': version}, 'publishedAt': published, 'isDefault': default}

def test_latest_stable_skips_prerelease_default():
    assert s.latest_stable([v('0.28.1', '2024'), v('0.29.0', '2025'), v('1.0.0.dev6', '2026', True)]) == '0.29.0'
    assert s.latest_stable([v('0.65b0', '2025'), v('0.66.0b1', '2026', True)]) == '0.66.0b1'  # nothing stable: keep the default
    assert s.latest_stable([v('v1.2.0', '2025', True), v('v1.3.0-rc.1', '2026')]) == 'v1.2.0'
    assert s.latest_stable([v('4.15.1', '2026', True)]) == '4.15.1'

def test_dep_info_skips_docker_and_actions():
    got = s.dep_info('docker', 'redis', 'alpine', lambda p: (_ for _ in ()).throw(AssertionError('no lookup')))
    assert got['license'] is None and got['license_of'] is None

def test_stack_record_keeps_license_when_analyser_fails(monkeypatch):
    monkeypatch.setattr(s, 'repo_license', lambda repo: 'MIT')
    def boom(repo, branch):
        raise RuntimeError('clone failed')
    rec = s.stack_record({'name': 'network-adapter', 'branch': 'development'}, analyse=boom)
    assert rec['license'] == 'MIT' and rec['dependencies'] == [] and rec['error'] == 'clone failed'

def test_repo_license(monkeypatch):
    monkeypatch.setattr(s.ac, 'api', lambda p: {'license': {'spdx_id': 'MIT'}})
    assert s.repo_license('na') == 'MIT'
    monkeypatch.setattr(s.ac, 'api', lambda p: {'license': {'spdx_id': 'NOASSERTION'}})
    assert s.repo_license('na') == 'Other'
    monkeypatch.setattr(s.ac, 'api', lambda p: None)
    assert s.repo_license('na') is None
