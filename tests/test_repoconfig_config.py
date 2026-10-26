import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import json
import pytest
from repoconfig import ConfigError, config

def n(**kw):
    return config.normalize({'organization': 'o', **kw})

def test_defaults_and_string_entries():
    c = n(repositories=['a', {'name': 'b', 'branch': 'development', 'tags': [' X ']}])
    assert c['repositories'][0] == {'name': 'a', 'branch': None, 'tags': [], 'security_workflow': None, 'releases': config.RELEASE_DEFAULTS}
    assert c['repositories'][1]['tags'] == ['X'] and c['sources'] == [] and c['exclude'] == []
    assert c['default_security_workflow'] == 'security.yml'

def test_duplicate_repository_is_an_error_even_with_different_case():
    with pytest.raises(ConfigError, match='listed twice'):
        n(repositories=['Network-Adapter', {'name': 'network-adapter', 'branch': 'x'}])

@pytest.mark.parametrize('bad,msg', [
    ({'repositories': [{'branch': 'x'}]}, 'repositories\\[0\\]: needs a "name"'),
    ({'repositories': [{'name': 'a', 'tags': 'DPG'}]}, 'tags'),
    ({'sources': [{'type': 'magic'}]}, 'sources\\[0\\]: "type" must be one of'),
    ({'sources': [{'type': 'query'}]}, 'needs "query"'),
    ({'sources': [{'type': 'project'}]}, 'needs "number"'),
    ({'sources': [{'type': 'query', 'query': 'q', 'fallback': 'a'}]}, 'fallback'),
    ({'exclude': 'a'}, 'exclude'),
    ({'dpg_repositories': ['a']}, 'no longer used'),
    ({'exclude_repositories': ['a']}, 'no longer used'),
    ({'release_branch_prefix': 'release-'}, 'branch_prefix'),
    ({'releases': {'sources': ['svn']}}, 'sources must be'),
    ({'releases': {'sources': []}}, 'sources must be'),
    ({'releases': {'sources': ['tag', 'tag']}}, 'sources must be'),
    ({'releases': {'max_versions': 0}}, 'max_versions'),
    ({'releases': {'max_versions': True}}, 'max_versions'),
    ({'releases': {'include_prereleases': 'yes'}}, 'include_prereleases'),
    ({'releases': {'tag_pattern': '('}}, 'not a valid regex'),
    ({'releases': {'tag_pattern': '^v(\\\\d+)$'}}, 'named group'),
    ({'releases': {'branch_prefix': ''}}, 'branch_prefix'),
    ({'releases': {'colour': 'red'}}, 'unknown releases setting'),
    ({'releases': 'tags'}, 'object or false'),
    ({'repositories': [{'name': 'a', 'releases': {'max_versions': -1}}]}, r'repositories\[0\] \(a\): releases.max_versions'),
])
def test_invalid_config_names_the_problem(bad, msg):
    with pytest.raises(ConfigError, match=msg):
        n(**bad)

def test_load_reports_invalid_json(tmp_path):
    p = tmp_path / 'c.json'; p.write_text('{oops')
    with pytest.raises(ConfigError, match='invalid JSON'):
        config.load(str(p))

def test_shipped_config_is_valid():
    c = config.load('config/repos.json')
    assert any(s['type'] == 'query' and s['tags'] == ['DPG'] for s in c['sources'])

def test_repo_release_settings_override_global_and_false_turns_off():
    c = n(releases={'max_versions': 4, 'sources': ['tag']}, repositories=['a', {'name': 'b', 'releases': {'sources': ['branch'], 'branch_prefix': 'rel/'}}, {'name': 'c', 'releases': False}])
    a, b, off = (r['releases'] for r in c['repositories'])
    assert a['max_versions'] == 4 and a['sources'] == ['tag']
    assert b['max_versions'] == 4 and b['sources'] == ['branch'] and b['branch_prefix'] == 'rel/'
    assert off is None

def test_global_releases_false_turns_off_everywhere_unless_a_repo_sets_its_own():
    c = n(releases=False, repositories=['a', {'name': 'b', 'releases': {'sources': ['tag']}}])
    assert c['releases'] is None and c['repositories'][0]['releases'] is None
    assert c['repositories'][1]['releases']['sources'] == ['tag'] and c['repositories'][1]['releases']['max_versions'] == 10

def test_license_policy_defaults_to_empty_lists():
    assert n()['licenses'] == {'green': [], 'yellow': [], 'red': []}

def test_license_policy_is_kept_and_trimmed():
    assert n(licenses={'green': [' MIT ', 'Apache-2.0'], 'red': ['GPL-*']})['licenses'] == {'green': ['MIT', 'Apache-2.0'], 'yellow': [], 'red': ['GPL-*']}

@pytest.mark.parametrize('bad,msg', [
    ({'green': ['MIT'], 'red': ['mit']}, 'in both green and red'),
    ({'blue': ['MIT']}, 'use only the keys'),
    ({'green': 'MIT'}, 'must be a list'),
    ({'green': ['']}, 'must be a list'),
])
def test_invalid_license_policy(bad, msg):
    with pytest.raises(ConfigError, match=msg):
        n(licenses=bad)
