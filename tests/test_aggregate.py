import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import aggregate_coverage as a

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
    monkeypatch.setattr(a, 'branch_coverage', lambda r, b, sha=None: {'coverage': 74.35, 'source': 'Codecov', 'commit': 'abc',
        'detail': {'lines': 10, 'hits': 7, 'files': 1, 'report_url': 'x'}, 'measured_at': 't'})
    monkeypatch.setattr(a, 'security_status', lambda r, b, w, sha=None: {'state': 'failing'})
    rec = a.inspect({'name': 'network-adapter', 'branch': 'development', 'security_workflow': 'security.yml'})
    assert rec['branch'] == 'development' and rec['coverage'] == 74.35 and rec['security']['state'] == 'failing'
    assert rec['coverage_badge_url'] == 'https://codecov.io/gh/OpenAgriNet/network-adapter/branch/development/graph/badge.svg'
    assert 'last_merged_pr' not in rec and 'main_commits_recent' not in rec and 'dev_coverage' not in rec

def test_collect_adds_main_view_and_reuses_record_when_branch_is_default(monkeypatch):
    calls = []
    def fake_inspect(t):
        calls.append((t['name'], t['branch']))
        return {'repository': t['name'], 'branch': t['branch']}
    monkeypatch.setattr(a, 'inspect', fake_inspect)
    monkeypatch.setattr(a, 'default_branch', lambda repo: 'main')
    monkeypatch.setattr(a, 'release_group', lambda t: {'repository': t['name'], 'versions': [{'branch': 'release-0.0.2'}]} if t['name'] == 'na' else None)
    targets = [{'name': 'na', 'branch': 'development', 'security_workflow': 'security.yml', 'tags': []},
               {'name': 'dss', 'branch': 'main', 'security_workflow': 'security.yml'}]
    got = a.collect(targets)
    assert [r['branch'] for r in got['repositories']] == ['development', 'main']
    assert [r['branch'] for r in got['main']] == ['main', 'main']
    assert [g['repository'] for g in got['releases']] == ['na']
    assert calls.count(('dss', 'main')) == 1  # main record reused, not measured twice

def test_collect_survives_api_error_for_one_repo(monkeypatch):
    def fake_inspect(t):
        if t['name'] == 'broken':
            raise RuntimeError('502 Bad Gateway')
        return {'repository': t['name'], 'branch': 'main'}
    monkeypatch.setattr(a, 'inspect', fake_inspect)
    monkeypatch.setattr(a, 'default_branch', lambda repo: 'main')
    monkeypatch.setattr(a, 'release_group', lambda t: None)
    got = a.collect([{'name': 'broken', 'branch': None, 'security_workflow': 'security.yml'},
                     {'name': 'ok', 'branch': None, 'security_workflow': 'security.yml'}])
    assert [r['repository'] for r in got['repositories']] == ['broken', 'ok']
    assert got['repositories'][0]['security']['state'] == 'unknown'
    assert got['repositories'][0]['coverage'] is None

def test_inspect_carries_tags_and_dpg_flag(monkeypatch):
    monkeypatch.setattr(a, 'resolve_branch', lambda r, b: ('main', False))
    rec = a.inspect({'name': 'x', 'branch': 'main', 'tags': ['DPG', 'core'], 'security_workflow': 'security.yml'})
    assert rec['tags'] == ['DPG', 'core'] and rec['dpg'] is True
    rec = a.inspect({'name': 'x', 'branch': 'main', 'tags': [], 'security_workflow': 'security.yml'})
    assert rec['dpg'] is False

def test_inspect_tag_uses_commit_and_has_no_live_badges(monkeypatch):
    seen = {}
    monkeypatch.setattr(a, 'resolve_branch', lambda r, b: (_ for _ in ()).throw(AssertionError('a tag is not a branch')))
    def cov(r, b, sha=None):
        seen['cov'] = (b, sha)
        return {'coverage': 95.4, 'source': 'Codecov', 'commit': sha, 'detail': None, 'measured_at': 't'}
    def sec(r, b, w, sha=None):
        seen['sec'] = (b, sha)
        return {'state': 'passing', 'badge_url': None}
    monkeypatch.setattr(a, 'branch_coverage', cov)
    monkeypatch.setattr(a, 'security_status', sec)
    rec = a.inspect({'name': 'dss', 'branch': 'v0.1.0', 'sha': 'abc123', 'tags': [], 'security_workflow': 'security.yml'})
    assert rec['ref_kind'] == 'tag' and rec['branch_exists'] is True and rec['coverage_badge_url'] is None
    assert seen == {'cov': ('v0.1.0', 'abc123'), 'sec': ('v0.1.0', 'abc123')}

def test_security_for_a_commit_queries_head_sha_and_has_no_badge(monkeypatch):
    paths = []
    def fake(path):
        paths.append(path)
        return {'workflow_runs': [{'conclusion': 'success', 'html_url': 'u', 'updated_at': 't'}]} if 'runs' in path else {'id': 1}
    monkeypatch.setattr(a, 'api', fake)
    s = a.security_status('dss', 'v0.1.0', 'security.yml', 'abc123')
    assert s['state'] == 'passing' and s['badge_url'] is None
    assert any('head_sha=abc123' in p and 'branch=' not in p for p in paths)

def test_release_group_measures_each_version_and_picks_newest_stable(monkeypatch):
    versions = [{'version': '0.2.0-RC1', 'ref': 'v0.2.0-RC1', 'ref_kind': 'tag', 'sha': 's3', 'kinds': ['tag'], 'prerelease': True, 'published_at': None},
                {'version': '0.1.0', 'ref': 'release-0.1.0', 'ref_kind': 'branch', 'sha': 's2', 'kinds': ['branch'], 'prerelease': False, 'published_at': None},
                {'version': '0.0.9', 'ref': 'v0.0.9', 'ref_kind': 'tag', 'sha': 's1', 'kinds': ['tag'], 'prerelease': False, 'published_at': None}]
    monkeypatch.setattr(a, 'find_versions', lambda org, repo, rc, get: {'versions': versions, 'total': 5})
    calls = []
    monkeypatch.setattr(a, 'safe_inspect', lambda t: calls.append((t['branch'], t.get('sha'))) or {'repository': t['name'], 'branch': t['branch']})
    g = a.release_group({'name': 'na', 'tags': ['DPG'], 'releases': {'sources': ['branch']}})
    assert calls == [('v0.2.0-RC1', 's3'), ('release-0.1.0', None), ('v0.0.9', 's1')]  # only tags are measured by commit
    assert g['default'] == '0.1.0' and g['not_measured'] == 2 and g['dpg'] is True and len(g['versions']) == 3

def test_release_group_none_when_releases_off_or_none_found(monkeypatch):
    assert a.release_group({'name': 'na', 'releases': None}) is None
    monkeypatch.setattr(a, 'find_versions', lambda *x: {'versions': [], 'total': 0})
    assert a.release_group({'name': 'na', 'releases': {}}) is None
    monkeypatch.setattr(a, 'find_versions', lambda *x: (_ for _ in ()).throw(RuntimeError('boom')))
    assert a.release_group({'name': 'na', 'releases': {}}) is None

def test_main_record_is_labelled_default_and_dev_record_keeps_how_it_was_found(monkeypatch):
    seen = []
    monkeypatch.setattr(a, 'safe_inspect', lambda t: seen.append((t['branch'], t.get('branch_source'))) or {'repository': t['name'], 'branch': t['branch'], 'branch_source': t.get('branch_source')})
    monkeypatch.setattr(a, 'default_branch', lambda repo: 'main')
    monkeypatch.setattr(a, 'release_group', lambda t: None)
    got = a.collect([{'name': 'na', 'branch': 'development', 'branch_source': 'pattern', 'tags': []}])
    assert seen == [('development', 'pattern'), ('main', 'default')]
    assert got['repositories'][0]['branch_source'] == 'pattern' and got['main'][0]['branch_source'] == 'default'

def test_collect_adds_resolved_release_sets(monkeypatch):
    monkeypatch.setattr(a, 'safe_inspect', lambda t: {'repository': t['name'], 'branch': 'main'})
    monkeypatch.setattr(a, 'default_branch', lambda repo: 'main')
    monkeypatch.setattr(a, 'release_group', lambda t: {'repository': t['name'], 'versions': [{'version': '0.1.0'}]})
    sets = [{'alias': 'v1', 'label': 'v1', 'current': False, 'tags': {'na': 'v0.1.0'}}]
    got = a.collect([{'name': 'na', 'branch': None, 'tags': [], 'releases': a.CFG['releases']}], sets)
    assert got['release_sets'] == [{'alias': 'v1', 'label': 'v1', 'current': True, 'repos': {'na': {'tag': 'v0.1.0', 'version': '0.1.0'}}}]

def test_collect_without_sets_has_an_empty_list(monkeypatch):
    monkeypatch.setattr(a, 'safe_inspect', lambda t: {'repository': t['name'], 'branch': 'main'})
    monkeypatch.setattr(a, 'default_branch', lambda repo: 'main')
    monkeypatch.setattr(a, 'release_group', lambda t: None)
    assert a.collect([{'name': 'na', 'branch': None, 'tags': []}])['release_sets'] == []
