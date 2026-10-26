import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from repoconfig import config
from repoconfig.resolve import resolve

def cfg(**kw):
    return config.normalize({'organization': 'o', **kw})

def search(*repos):
    return lambda path: {'items': [{'name': n, 'private': p} for n, p in repos]}

def run(c, get=search(), log=None, token=None):
    logs = [] if log is None else log
    return resolve(c, 'o', get, token, log=logs.append), logs

Q = {'type': 'query', 'query': 'q', 'tags': ['DPG']}

def names(got):
    return [t['name'] for t in got]

def test_explicit_repos_first_then_discovered_with_source_tags():
    got, _ = run(cfg(repositories=[{'name': 'a', 'branch': 'development'}], sources=[Q]), search(('b', False), ('a', False)))
    assert names(got) == ['a', 'b']
    assert got[0] == {'name': 'a', 'branch': 'development', 'tags': ['DPG'], 'security_workflow': 'security.yml', 'releases': config.RELEASE_DEFAULTS}
    assert got[1]['branch'] is None and got[1]['tags'] == ['DPG']

def test_explicit_branch_beats_source_branch_and_tags_merge():
    c = cfg(repositories=[{'name': 'a', 'branch': 'development', 'tags': ['core']}], sources=[{**Q, 'branch': 'main'}])
    got, _ = run(c, search(('A', False)))  # different case, same repo
    assert names(got) == ['a'] and got[0]['branch'] == 'development' and got[0]['tags'] == ['core', 'DPG']

def test_two_sources_union_tags_first_branch_wins_and_clash_is_logged():
    c = cfg(sources=[{**Q, 'branch': 'main'}, {'type': 'query', 'query': 'q2', 'tags': ['infra'], 'branch': 'develop'}])
    got, logs = run(c, search(('a', False)))
    assert got[0]['tags'] == ['DPG', 'infra'] and got[0]['branch'] == 'main'
    assert any('clash' in l and 'develop' in l for l in logs)

def test_exclude_beats_explicit_and_sources():
    c = cfg(repositories=['a'], sources=[Q], exclude=['A', 'c'])
    got, logs = run(c, search(('a', False), ('b', False), ('c', False)))
    assert names(got) == ['b'] and any('excluded' in l for l in logs)

def test_private_discovered_repos_skipped_but_explicit_kept_and_tagged():
    got, logs = run(cfg(repositories=['priv'], sources=[Q]), search(('priv', True), ('other', True)))
    assert names(got) == ['priv'] and got[0]['tags'] == ['DPG']
    assert any('skipping private repo other' in l for l in logs)

def test_failed_source_uses_fallback_and_keeps_other_sources():
    def get(path):
        raise RuntimeError('rate limited')
    c = cfg(sources=[{**Q, 'fallback': ['x', 'y']}, {'type': 'query', 'query': 'q2', 'tags': ['ok'], 'enabled': False}])
    got, logs = run(c, get)
    assert names(got) == ['x', 'y'] and got[0]['tags'] == ['DPG']
    assert any('WARN' in l and 'fallback' in l for l in logs)

def test_failed_source_without_fallback_leaves_explicit_repos():
    def get(path):
        raise RuntimeError('boom')
    got, logs = run(cfg(repositories=['a'], sources=[Q]), get)
    assert names(got) == ['a'] and any('no fallback' in l for l in logs)

def test_project_source_without_token_falls_back():
    c = cfg(sources=[{'type': 'project', 'number': 9, 'tags': ['DPG'], 'fallback': ['z']}])
    got, logs = run(c)
    assert names(got) == ['z'] and any('DPG_PROJECT_TOKEN' in l for l in logs)

def test_disabled_source_is_ignored():
    got, _ = run(cfg(sources=[{**Q, 'enabled': False}]), search(('a', False)))
    assert got == []

def test_per_repo_security_workflow_and_default():
    c = cfg(repositories=[{'name': 'a', 'security_workflow': 'sec.yml'}, 'b'], defaults={'security_workflow': 'scan.yml'})
    got, _ = run(c)
    assert [t['security_workflow'] for t in got] == ['sec.yml', 'scan.yml']

def test_releases_setting_flows_to_targets_listed_off_and_discovered():
    c = cfg(releases={'max_versions': 3}, repositories=[{'name': 'a', 'releases': {'sources': ['tag']}}, {'name': 'b', 'releases': False}, 'c'], sources=[Q])
    got, _ = run(c, search(('d', False)))
    by = {t['name']: t['releases'] for t in got}
    assert by['a']['sources'] == ['tag'] and by['a']['max_versions'] == 3
    assert by['b'] is None
    assert by['c']['max_versions'] == 3 and by['d']['max_versions'] == 3

def test_query_matching_nothing_uses_the_fallback_and_warns():
    got, logs = run(cfg(sources=[{**Q, 'fallback': ['x']}]), search())
    assert names(got) == ['x'] and any('WARN' in l and 'no repositories' in l for l in logs)

def test_query_matching_nothing_without_fallback_is_not_an_error():
    got, logs = run(cfg(sources=[Q]), search())
    assert got == [] and not any('WARN' in l for l in logs)
