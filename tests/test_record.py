import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import record as r
import pytest

@pytest.fixture(autouse=True)
def no_star_lookups(monkeypatch):
    monkeypatch.setattr(r, 'annotate_stars', lambda deps: None)
    monkeypatch.setattr(r, 'fill_licenses', lambda deps: None)
    monkeypatch.setattr(r, 'explain', lambda deps: None)
    monkeypatch.setattr(r, 'annotate_terraform', lambda deps: None)
    monkeypatch.setattr(r, 'annotate_releases', lambda deps: None)   # reasons have their own tests
    monkeypatch.setattr(r, 'repo_stars', lambda repo: None)

def test_stack_record_keeps_license_when_analyser_fails(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: 'MIT')
    def boom(repo, branch):
        raise RuntimeError('clone failed')
    rec = r.stack_record({'name': 'network-adapter', 'branch': 'development'}, analyse=boom)
    assert rec['license'] == 'MIT' and rec['dependencies'] == [] and rec['error'] == 'clone failed'

def test_stack_record_adds_dependency_info(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    raw = {'languages': {'Go': 3}, 'techs': ['golang'], 'dependencies': [['golang', 'github.com/a/b', 'v1.0.0']]}
    rec = r.stack_record({'name': 'na', 'branch': 'development'}, analyse=lambda repo, branch: raw,
                         info=lambda e, n, v: {'name': n, 'license': 'MIT'}, vulns=lambda deps: None)
    assert rec['languages'] == [('Go', 3)] and rec['dependencies'] == [{'name': 'github.com/a/b', 'license': 'MIT', 'groups': [], 'short': 'b', 'license_class': 'unclassified'}] and rec['error'] is None

def test_stack_record_runs_vulnerability_check_on_the_dependencies(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    raw = {'dependencies': [['python', 'jinja2', '3.1.0']]}
    def vulns(deps):
        for d in deps:
            d['vulns'] = {'count': 2}
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: raw,
                         info=lambda e, n, v: {'name': n}, vulns=vulns)
    assert rec['dependencies'] == [{'name': 'jinja2', 'groups': [], 'short': 'jinja2', 'vulns': {'count': 2}, 'license_class': None}]

def test_repo_license(monkeypatch):
    monkeypatch.setattr(r.github, 'api', lambda p: {'license': {'spdx_id': 'MIT'}})
    assert r.repo_license('na') == 'MIT'
    monkeypatch.setattr(r.github, 'api', lambda p: {'license': {'spdx_id': 'NOASSERTION'}})
    assert r.repo_license('na') == 'Other'
    monkeypatch.setattr(r.github, 'api', lambda p: None)
    assert r.repo_license('na') is None

def test_stack_record_classifies_repo_and_dependency_licenses(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: 'MIT')
    policy = {'green': ['MIT'], 'yellow': [], 'red': ['GPL-*']}
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: {'dependencies': [['npm', 'a', '1'], ['npm', 'b', '1'], ['docker', 'c', '1']]},
                         info=lambda e, n, v: {'name': n, 'license': {'a': 'MIT', 'b': 'GPL-3.0-only', 'c': None}[n]}, vulns=lambda deps: None, policy=policy)
    assert rec['license_class'] == 'green'
    assert [(d['name'], d['license_class']) for d in rec['dependencies']] == [('c', None), ('a', 'green'), ('b', 'red')]  # sorted by ecosystem

def test_stack_record_survives_default_branch_failure(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: 'MIT')
    def boom(repo):
        raise RuntimeError('502')
    monkeypatch.setattr(r.github, 'default_branch', boom)
    rec = r.stack_record({'name': 'na', 'branch': None}, analyse=lambda *a: {})
    assert rec['license'] == 'MIT' and rec['error'] == '502' and rec['dependencies'] == []

def test_stack_record_runs_the_actions_lookup_before_classifying(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    raw = {'dependencies': [['githubAction', 'actions/cache', 'v4']]}
    def actions(deps):
        for d in deps:
            d['license'] = 'MIT'
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: raw,
                         info=lambda e, n, v: {'name': n}, vulns=lambda deps: None, actions=actions, policy={'green': ['MIT']})
    assert rec['dependencies'] == [{'name': 'actions/cache', 'groups': [], 'short': 'cache', 'license': 'MIT', 'license_class': 'green'}]

def test_stack_record_labels_groups_from_the_manifests(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    raw = {'dependencies': [['npm', 'vite', '^5.0.0'], ['docker', 'redis', '7']],
           'manifests': {('npm', 'vite'): {'groups': ['dev'], 'installed': '5.4.2', 'sources': ['package.json']}}}
    seen = {}
    def vulns(deps):
        seen.update({d['name']: d.get('installed') for d in deps})
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: raw,
                         info=lambda e, n, v: {'ecosystem': e, 'name': n, 'version': v}, vulns=vulns, actions=lambda d: None, images=lambda d: None)
    by = {d['name']: d for d in rec['dependencies']}; vite, redis = by['vite'], by['redis']
    assert vite['groups'] == ['dev'] and vite['installed'] == '5.4.2' and redis['groups'] == ['runtime']
    assert seen == {'vite': '5.4.2', 'redis': None}   # groups and installed are known before the vulnerability check

def test_stack_record_adds_packages_the_analyser_missed(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    raw = {'dependencies': [['python', 'fastapi', '>=0.1']],
           'manifests': {('python', 'fastapi'): {'name': 'fastapi', 'declared': '>=0.1', 'installed': None, 'groups': ['main'], 'sources': ['pyproject.toml']},
                         ('python', 'pytest'): {'name': 'pytest', 'declared': '>=9.1.1', 'installed': '9.1.2', 'groups': ['dev'], 'sources': ['pyproject.toml']},
                         ('githubRelease', 'aquasecurity/trivy'): {'name': 'aquasecurity/trivy', 'declared': 'latest', 'installed': None, 'groups': ['security'], 'sources': ['.github/workflows/security.yml']}}}
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: raw,
                         info=lambda e, n, v: {'ecosystem': e, 'name': n, 'version': v}, vulns=lambda d: None, actions=lambda d: None, images=lambda d: None)
    by = {d['name']: d for d in rec['dependencies']}
    assert by['pytest']['groups'] == ['dev'] and by['pytest']['installed'] == '9.1.2'
    assert by['aquasecurity/trivy']['groups'] == ['security'] and by['aquasecurity/trivy']['version'] == 'latest'

def test_a_repo_and_a_dependency_without_a_license_take_the_no_license_class(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    monkeypatch.setattr(r, 'explain', __import__('stackinfo.rules.reasons', fromlist=['explain']).explain)
    raw = {'dependencies': [['npm', 'nolicense', '1.0.0'], ['npm', 'broken', '1.0.0'], ['npm', 'mit', '1.0.0']]}
    info = lambda e, n, v: {'ecosystem': e, 'name': n, 'version': v, 'latest': v, 'license': 'MIT' if n == 'mit' else None,
                            'license_of': 'error' if n == 'broken' else None}
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: raw, info=info, vulns=lambda d: None,
                         actions=lambda d: None, images=lambda d: None, policy={'green': ['MIT'], 'no_license': 'red'})
    by = {d['name']: d for d in rec['dependencies']}
    assert rec['license_class'] == 'red'                                   # no LICENSE file
    assert by['nolicense']['license_class'] == 'red' and by['mit']['license_class'] == 'green'
    assert by['broken']['license_class'] is None                           # a failed lookup is not a missing license

def test_a_failed_repo_license_lookup_is_not_no_license(monkeypatch):
    def boom(repo):
        raise RuntimeError('502')
    monkeypatch.setattr(r, 'repo_license', boom)
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: {}, policy={'no_license': 'red'})
    assert rec['license_class'] is None
