import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from repoconfig import config
from repoconfig.resolve import resolve, SourceError

def cfg(**kw):
    return config.normalize({'organization': 'o', **kw})

def api(repos=(), branches=None, fail_search=None):
    """repos: (name, private) the query finds; branches: repo -> branch names."""
    branches = branches or {}
    def get(path):
        if path.startswith('/search/repositories'):
            if fail_search:
                raise RuntimeError(fail_search)
            return {'items': [{'name': n, 'private': p} for n, p in repos]}
        if '/branches?' in path:
            repo = path.split('/repos/o/')[1].split('/')[0]
            if isinstance(branches.get(repo), Exception):
                raise branches[repo]
            return [{'name': b} for b in branches.get(repo, ['main'])]
        raise AssertionError(path)
    return get

Q = {'type': 'query', 'query': 'q', 'tags': ['DPG']}

def run(c, get=None, token=None):
    logs = []
    return resolve(c, 'o', get or api(), token, log=logs.append), logs

def names(got):
    return [t['name'] for t in got]

def by(got):
    return {t['name']: t for t in got}

def test_repos_come_from_the_query_and_carry_its_tags():
    got, _ = run(cfg(sources=[Q]), api([('a', False), ('b', False)]))
    assert names(got) == ['a', 'b'] and got[0]['tags'] == ['DPG'] and got[0]['security_workflow'] == 'security.yml'
    assert 'fallback' not in got[0] and got[0]['releases'] == config.RELEASE_DEFAULTS

def test_custom_repositories_come_first_and_merge_tags_with_the_query():
    got, _ = run(cfg(repositories=[{'name': 'x', 'tags': ['core']}, {'name': 'a', 'tags': ['core']}], sources=[Q]), api([('b', False), ('A', False)]))
    assert names(got) == ['x', 'a', 'b'] and by(got)['a']['tags'] == ['core', 'DPG'] and by(got)['x']['tags'] == ['core']

def test_two_sources_union_tags():
    c = cfg(sources=[Q, {'type': 'query', 'query': 'q2', 'tags': ['infra']}])
    got, _ = run(c, api([('a', False)]))
    assert got[0]['tags'] == ['DPG', 'infra']

def test_exclude_beats_explicit_and_sources():
    got, logs = run(cfg(repositories=['a'], sources=[Q], exclude=['A', 'c']), api([('a', False), ('b', False), ('c', False)]))
    assert names(got) == ['b'] and any('excluded' in l for l in logs)

def test_private_discovered_repos_skipped_but_custom_ones_kept_and_tagged():
    got, logs = run(cfg(repositories=['priv'], sources=[Q]), api([('priv', True), ('other', True)]))
    assert names(got) == ['priv'] and got[0]['tags'] == ['DPG']
    assert any('skipping private repo other' in l for l in logs)

def test_disabled_source_is_ignored():
    got, _ = run(cfg(sources=[{**Q, 'enabled': False}]), api([('a', False)]))
    assert got == []

def test_a_failing_source_stops_the_run_with_a_message_naming_it():
    with pytest.raises(SourceError, match='query source #1 failed: rate limited.*keeps its last data'):
        run(cfg(repositories=['a'], sources=[Q]), api(fail_search='rate limited'))

def test_project_source_without_token_stops_the_run():
    with pytest.raises(SourceError, match='DPG_PROJECT_TOKEN'):
        run(cfg(sources=[{'type': 'project', 'number': 9, 'tags': ['DPG']}]))

def test_a_query_that_finds_nothing_only_warns():
    got, logs = run(cfg(repositories=['a'], sources=[Q]), api([]))
    assert names(got) == ['a'] and any('WARN' in l and 'found nothing' in l for l in logs)

def test_configured_dev_branch_wins_and_is_not_looked_up():
    def get(path):
        assert '/branches?' not in path
        return {'items': []}
    got, _ = run(cfg(repositories=[{'name': 'a', 'dev_branch': 'staging'}]), get)
    assert (got[0]['branch'], got[0]['branch_source'], got[0]['dev_branch']) == ('staging', 'configured', 'staging')

def test_development_branch_is_found_by_the_pattern():
    got, _ = run(cfg(sources=[Q]), api([('a', False), ('b', False)], {'a': ['main', 'development', 'release-0.2.0'], 'b': ['main', 'develop']}))
    assert [(t['branch'], t['branch_source']) for t in got] == [('development', 'pattern'), ('develop', 'pattern')]

def test_no_matching_branch_means_the_default_branch_and_says_so():
    got, _ = run(cfg(sources=[Q]), api([('a', False)], {'a': ['main', 'release-1.0.0', 'feature-dev-x']}))
    assert (got[0]['branch'], got[0]['branch_source']) == (None, 'default')   # the pattern is anchored, so feature-dev-x does not match

def test_several_matches_use_the_first_alphabetically_and_log_it():
    got, logs = run(cfg(sources=[Q]), api([('a', False)], {'a': ['main', 'development', 'dev']}))
    assert got[0]['branch'] == 'dev' and any('several branches match' in l for l in logs)

def test_custom_pattern():
    got, _ = run(cfg(sources=[Q], branches={'development': '^integration$'}), api([('a', False)], {'a': ['main', 'integration', 'development']}))
    assert got[0]['branch'] == 'integration'

def test_branch_listing_failure_falls_back_to_the_default_branch():
    got, logs = run(cfg(sources=[Q]), api([('a', False)], {'a': RuntimeError('502')}))
    assert got[0]['branch_source'] == 'default' and any('could not list branches' in l for l in logs)

def test_per_repo_security_workflow_default_and_override():
    c = cfg(repositories=[{'name': 'a', 'security_workflow': 'sec.yml'}, 'b'], security={'workflow': 'scan.yml'})
    got, _ = run(c)
    assert [t['security_workflow'] for t in got] == ['sec.yml', 'scan.yml']

def test_releases_setting_flows_to_targets_custom_off_and_discovered():
    c = cfg(releases={'max_versions': 3}, repositories=[{'name': 'a', 'releases': {'sources': ['tag']}}, {'name': 'b', 'releases': False}, 'c'], sources=[Q])
    got, _ = run(c, api([('d', False)]))
    rel = {t['name']: t['releases'] for t in got}
    assert rel['a']['sources'] == ['tag'] and rel['a']['max_versions'] == 3
    assert rel['b'] is None
    assert rel['c']['max_versions'] == 3 and rel['d']['max_versions'] == 3
