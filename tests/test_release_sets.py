import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from repoconfig.config import RELEASE_DEFAULTS as R
from releasefind.sets import resolve_sets, identity

def group(repo, *versions):
    return {'repository': repo, 'versions': [{'version': v} for v in versions]}

def sset(alias, tags, current=False, label=None):
    return {'alias': alias, 'label': label or alias, 'current': current, 'tags': tags}

GROUPS = [group('network-adapter', '0.2.0', '0.1.0'), group('knowledge-provider', '0.1.0'), group('helmcharts', '0.1.0')]

def test_names_for_the_same_version_have_one_identity():
    assert identity('v0.1.0', R) == identity('0.1.0', R) == identity('release-0.1.0', R) == identity('0.1', R)
    assert identity('fork-point', R) is None and identity('0.1.0-RC1', R) != identity('0.1.0', R)

def test_each_repo_maps_to_its_own_tag_name_style():
    got = resolve_sets([sset('v1', {'network-adapter': '0.1.0', 'knowledge-provider': 'v0.1.0'})], GROUPS, {})
    assert got[0]['repos'] == {'network-adapter': {'tag': '0.1.0', 'version': '0.1.0'}, 'knowledge-provider': {'tag': 'v0.1.0', 'version': '0.1.0'}}

def test_repo_names_are_matched_ignoring_case_and_reported_as_the_dashboard_spells_them():
    got = resolve_sets([sset('v1', {'Network-Adapter': '0.2.0'})], GROUPS, {})
    assert got[0]['repos'] == {'network-adapter': {'tag': '0.2.0', 'version': '0.2.0'}}

def test_a_tag_discovery_did_not_find_has_no_version():
    got = resolve_sets([sset('v1', {'network-adapter': '0.0.9', 'ghost': '1.0.0', 'helmcharts': 'fork-point'})], GROUPS, {})[0]
    assert got['repos'] == {'network-adapter': {'tag': '0.0.9', 'version': None}, 'ghost': {'tag': '1.0.0', 'version': None}, 'helmcharts': {'tag': 'fork-point', 'version': None}}

def test_current_is_the_marked_set_else_the_last_listed():
    sets = [sset('v1', {'a': '1'}), sset('v2', {'a': '2'}), sset('v3', {'a': '3'})]
    assert [s['current'] for s in resolve_sets(sets, [], {})] == [False, False, True]
    sets[0]['current'] = True
    assert [s['current'] for s in resolve_sets(sets, [], {})] == [True, False, False]

def test_no_sets_gives_nothing():
    assert resolve_sets([], GROUPS, {}) == []

def test_a_repos_own_tag_pattern_is_used():
    rc = {**R, 'tag_pattern': r'^rel/(?P<version>\d+\.\d+\.\d+)$'}
    got = resolve_sets([sset('v1', {'x': 'rel/1.2.3'})], [group('x', '1.2.3')], {'x': rc})
    assert got[0]['repos']['x'] == {'tag': 'rel/1.2.3', 'version': '1.2.3'}
