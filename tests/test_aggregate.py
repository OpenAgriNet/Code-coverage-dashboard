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

def fake_api(responses):
    return lambda path: next((v for k, v in responses.items() if path.startswith(k)), None)

def test_security_passing(monkeypatch):
    monkeypatch.setattr(a, 'api', fake_api({
        '/repos/OpenAgriNet/dss/actions/workflows/security.yml/runs': {'workflow_runs': [
            {'status': 'completed', 'conclusion': 'success', 'html_url': 'u', 'updated_at': 't'}]},
        '/repos/OpenAgriNet/dss/actions/workflows/security.yml': {'id': 1}}))
    s = a.security_status('dss', 'main', 'security.yml')
    assert s['state'] == 'passing' and s['run_url'] == 'u'
    assert s['badge_url'] == 'https://github.com/OpenAgriNet/dss/actions/workflows/security.yml/badge.svg?branch=main'

def test_security_never_ran_on_branch(monkeypatch):
    monkeypatch.setattr(a, 'api', fake_api({
        '/repos/OpenAgriNet/na/actions/workflows/security.yml/runs': {'workflow_runs': []},
        '/repos/OpenAgriNet/na/actions/workflows/security.yml': {'id': 1}}))
    assert a.security_status('na', 'development', 'security.yml')['state'] == 'no runs'

def test_security_workflow_missing(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda path: None)
    s = a.security_status('experience-api', 'main', 'security.yml')
    assert s['state'] == 'no workflow' and s['badge_url'] is None

def test_inspect_record_shape(monkeypatch):
    monkeypatch.setattr(a, 'resolve_branch', lambda r, b: ('development', True))
    monkeypatch.setattr(a, 'branch_coverage', lambda r, b: {'coverage': 74.35, 'source': 'Codecov', 'commit': 'abc',
        'detail': {'lines': 10, 'hits': 7, 'files': 1, 'report_url': 'x'}, 'measured_at': 't'})
    monkeypatch.setattr(a, 'security_status', lambda r, b, w: {'state': 'failing'})
    rec = a.inspect({'name': 'network-adapter', 'branch': 'development', 'security_workflow': 'security.yml'})
    assert rec['branch'] == 'development' and rec['coverage'] == 74.35 and rec['security']['state'] == 'failing'
    assert rec['coverage_badge_url'] == 'https://codecov.io/gh/OpenAgriNet/network-adapter/branch/development/graph/badge.svg'
    assert 'last_merged_pr' not in rec and 'main_commits_recent' not in rec and 'dev_coverage' not in rec

def test_latest_release_picks_highest_version(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda p: [{'name': 'release-0.0.9'}, {'name': 'release-0.0.10'}, {'name': 'main'}])
    assert a.latest_release_branch('na', 'release-') == 'release-0.0.10'

def test_latest_release_none_when_no_release_branch(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda p: [{'name': 'main'}])
    assert a.latest_release_branch('kp', 'release-') is None

def test_collect_adds_main_view_and_reuses_record_when_branch_is_default(monkeypatch):
    calls = []
    def fake_inspect(t):
        calls.append((t['name'], t['branch']))
        return {'repository': t['name'], 'branch': t['branch']}
    monkeypatch.setattr(a, 'inspect', fake_inspect)
    monkeypatch.setattr(a, 'default_branch', lambda repo: 'main')
    monkeypatch.setattr(a, 'latest_release_branch', lambda repo, prefix: 'release-0.0.2' if repo == 'na' else None)
    targets = [{'name': 'na', 'branch': 'development', 'security_workflow': 'security.yml'},
               {'name': 'dss', 'branch': 'main', 'security_workflow': 'security.yml'}]
    got = a.collect(targets, 'release-')
    assert [r['branch'] for r in got['repositories']] == ['development', 'main']
    assert [r['branch'] for r in got['main']] == ['main', 'main']
    assert [r['branch'] for r in got['releases']] == ['release-0.0.2']
    assert calls.count(('dss', 'main')) == 1  # main record reused, not measured twice
