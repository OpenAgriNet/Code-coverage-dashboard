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
                         info=lambda e, n, v: {'name': n, 'license': 'MIT'})
    assert rec['languages'] == [('Go', 3)] and rec['dependencies'] == [{'name': 'github.com/a/b', 'license': 'MIT'}] and rec['error'] is None

def test_repo_license(monkeypatch):
    monkeypatch.setattr(r.ac, 'api', lambda p: {'license': {'spdx_id': 'MIT'}})
    assert r.repo_license('na') == 'MIT'
    monkeypatch.setattr(r.ac, 'api', lambda p: {'license': {'spdx_id': 'NOASSERTION'}})
    assert r.repo_license('na') == 'Other'
    monkeypatch.setattr(r.ac, 'api', lambda p: None)
    assert r.repo_license('na') is None
