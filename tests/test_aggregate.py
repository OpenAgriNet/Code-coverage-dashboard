import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import aggregate_coverage as a

def test_repo_targets_mixes_objects_strings_and_project_repos():
    cfg = {'repositories': [{'name': 'network-adapter', 'branch': 'development'}, 'knowledge-provider'],
           'exclude_repositories': ['engineering-tracker']}
    got = a.repo_targets(cfg, ['network-adapter', 'helmcharts', 'engineering-tracker'])
    assert got == [
        {'name': 'network-adapter', 'branch': 'development', 'security_workflow': 'security.yml'},
        {'name': 'knowledge-provider', 'branch': None, 'security_workflow': 'security.yml'},
        {'name': 'helmcharts', 'branch': None, 'security_workflow': 'security.yml'},
    ]

def test_plain_string_entry_uses_default_branch():
    assert a.repo_targets({'repositories': ['x']}, [])[0]['branch'] is None

def test_resolve_branch_reports_missing_branch(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda path: None)  # GitHub 404 for the branch
    assert a.resolve_branch('network-adapter', 'devlopment') == ('devlopment', False)
