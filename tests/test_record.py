import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import record as r

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
    assert rec['languages'] == [('Go', 3)] and rec['dependencies'] == [{'name': 'github.com/a/b', 'license': 'MIT', 'license_class': 'unclassified'}] and rec['error'] is None

def test_stack_record_runs_vulnerability_check_on_the_dependencies(monkeypatch):
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    raw = {'dependencies': [['python', 'jinja2', '3.1.0']]}
    def vulns(deps):
        for d in deps:
            d['vulns'] = {'count': 2}
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: raw,
                         info=lambda e, n, v: {'name': n}, vulns=vulns)
    assert rec['dependencies'] == [{'name': 'jinja2', 'vulns': {'count': 2}, 'license_class': None}]

def test_repo_license(monkeypatch):
    monkeypatch.setattr(r.ac, 'api', lambda p: {'license': {'spdx_id': 'MIT'}})
    assert r.repo_license('na') == 'MIT'
    monkeypatch.setattr(r.ac, 'api', lambda p: {'license': {'spdx_id': 'NOASSERTION'}})
    assert r.repo_license('na') == 'Other'
    monkeypatch.setattr(r.ac, 'api', lambda p: None)
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
    monkeypatch.setattr(r.ac, 'default_branch', boom)
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
    assert rec['dependencies'] == [{'name': 'actions/cache', 'license': 'MIT', 'license_class': 'green'}]
