import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import json
import pytest
from repoconfig import ConfigError, config

def n(**kw):
    return config.normalize({'organization': 'o', **kw})

def test_defaults_and_string_entries():
    c = n(repositories=['a', {'name': 'b', 'dev_branch': 'development', 'tags': [' X ']}])
    assert c['repositories'][0] == {'name': 'a', 'dev_branch': None, 'tags': [], 'security_workflow': None, 'releases': config.RELEASE_DEFAULTS}
    assert c['repositories'][1]['dev_branch'] == 'development'
    assert c['repositories'][1]['tags'] == ['X'] and c['sources'] == [] and c['exclude'] == []
    assert c['default_security_workflow'] == 'security.yml'

def test_duplicate_repository_is_an_error_even_with_different_case():
    with pytest.raises(ConfigError, match='listed twice'):
        n(repositories=['Network-Adapter', {'name': 'network-adapter', 'dev_branch': 'x'}])

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
    assert n()['licenses'] == {'green': [], 'yellow': [], 'red': [], 'labels': config.LICENSE_LABELS}

def test_license_policy_is_kept_and_trimmed():
    assert n(licenses={'green': [' MIT ', 'Apache-2.0'], 'red': ['GPL-*']})['licenses'] == {'green': ['MIT', 'Apache-2.0'], 'yellow': [], 'red': ['GPL-*'], 'labels': config.LICENSE_LABELS}

@pytest.mark.parametrize('bad,msg', [
    ({'green': ['MIT'], 'red': ['mit']}, 'in both green and red'),
    ({'blue': ['MIT']}, 'use only the keys'),
    ({'green': 'MIT'}, 'must be a list'),
    ({'green': ['']}, 'must be a list'),
    ({'labels': {'blue': 'Fine'}}, 'licenses.labels'),
    ({'labels': {'red': ''}}, 'licenses.labels'),
])
def test_invalid_license_policy(bad, msg):
    with pytest.raises(ConfigError, match=msg):
        n(licenses=bad)

def test_stack_settings_default_to_ignoring_markup_and_tooling():
    s = n()['stack']
    assert 'Markdown' in s['ignore_languages'] and 'YAML' in s['ignore_languages'] and 'github' in s['ignore_techs'] and s['max_languages'] == 3

def test_stack_settings_can_be_overridden_one_key_at_a_time():
    s = n(stack={'max_languages': 5, 'ignore_languages': ['Markdown']})['stack']
    assert s['max_languages'] == 5 and s['ignore_languages'] == ['Markdown'] and 'github' in s['ignore_techs']

@pytest.mark.parametrize('bad,msg', [
    ({'colour': 1}, 'use only the keys'),
    ({'max_techs': 0}, 'max_techs'),
    ({'max_languages': True}, 'max_languages'),
    ({'ignore_techs': 'github'}, 'must be a list'),
    ({'min_share': 1.5}, 'min_share'),
    ({'min_share': -0.1}, 'min_share'),
    ({'min_share': True}, 'min_share'),
    ({'min_share': '10%'}, 'min_share'),
])
def test_invalid_stack_settings(bad, msg):
    with pytest.raises(ConfigError, match=msg):
        n(stack=bad)


@pytest.mark.parametrize('bad,msg', [
    ({'repositories': [{'name': 'a', 'branch': 'main'}]}, 'repositories\\[0\\] \\(a\\): "branch" is no longer used.*dev_branch'),
    ({'repositories': [{'name': 'a', 'devbranch': 'x'}]}, 'unknown key\\(s\\) devbranch; allowed: dev_branch'),
    ({'repositories': [{'name': 'a', 'dev_branch': ''}]}, 'dev_branch'),
    ({'repositories': [{'name': 'a', 'dev_branch': 3}]}, 'dev_branch'),
    ({'sources': [{'type': 'query', 'query': 'q', 'fallback': ['a']}]}, '"fallback" is no longer used.*last data'),
    ({'sources': [{'type': 'query', 'query': 'q', 'branch': 'dev'}]}, '"branch" is no longer used.*dev_branch'),
    ({'sources': [{'type': 'query', 'query': 'q', 'tag': ['x']}]}, 'unknown key\\(s\\) tag'),
    ({'sources': [{'type': 'project', 'number': 9, 'query': 'q'}]}, 'unknown key\\(s\\) query'),
    ({'defaults': {'security_workflow': 'x.yml'}}, '"defaults" is no longer used.*security'),
    ({'workflow_names': ['CI']}, '"workflow_names" is no longer used.*coverage'),
    ({'artifact_name_hints': []}, '"artifact_name_hints" is no longer used.*coverage'),
    ({'branches': {'development': '('}}, 'not a valid regex'),
    ({'branches': {'production': 'x'}}, 'use only the key "development"'),
    ({'coverage': {'workflows': ['CI']}}, 'use only the keys workflow_names, artifact_name_hints'),
    ({'coverage': {'workflow_names': 'CI'}}, 'must be a list of names'),
    ({'security': {'workflow': ''}}, 'workflow file name'),
    ({'security': {'file': 'x'}}, 'use only the key "workflow"'),
])
def test_new_blocks_and_removed_keys_are_reported_clearly(bad, msg):
    with pytest.raises(ConfigError, match=msg):
        n(**bad)

def test_grouped_settings_have_defaults():
    c = n()
    assert c['branches'] == {'development': config.DEV_BRANCH_DEFAULT}
    assert c['coverage'] == {'workflow_names': ['CI'], 'artifact_name_hints': []}
    assert c['security'] == {'workflow': 'security.yml'} and c['default_security_workflow'] == 'security.yml'
    assert c['release_sets'] == []

def test_grouped_settings_can_be_set():
    c = n(branches={'development': '^integration$'}, coverage={'workflow_names': ['Tests']}, security={'workflow': 'scan.yml'})
    assert c['branches']['development'] == '^integration$' and c['coverage']['workflow_names'] == ['Tests'] and c['coverage']['artifact_name_hints'] == []
    assert c['default_security_workflow'] == 'scan.yml'

def test_default_development_pattern_matches_the_usual_names_only():
    import re
    p = config.DEV_BRANCH_DEFAULT
    assert all(re.search(p, b) for b in ('dev', 'develop', 'development'))
    assert not any(re.search(p, b) for b in ('main', 'devops', 'feature/dev', 'release-1.0.0', 'development-2'))

SETS = [{'alias': 'v1', 'tags': {'network-adapter': '0.1.0', 'knowledge-provider': 'v0.1.0'}}, {'alias': 'v2', 'label': 'Release 2', 'tags': {'network-adapter': '0.2.0'}}]

def test_release_sets_keep_order_labels_and_tags():
    got = n(release_sets=SETS)['release_sets']
    assert [s['alias'] for s in got] == ['v1', 'v2'] and [s['label'] for s in got] == ['v1', 'Release 2']
    assert got[0]['tags'] == {'network-adapter': '0.1.0', 'knowledge-provider': 'v0.1.0'} and not any(s['current'] for s in got)

def test_one_release_set_can_be_marked_current():
    got = n(release_sets=[SETS[0], {**SETS[1], 'current': True}])['release_sets']
    assert [s['current'] for s in got] == [False, True]

@pytest.mark.parametrize('bad,msg', [
    ([{'tags': {'a': '1'}}], 'needs an "alias"'),
    ([{'alias': ' ', 'tags': {'a': '1'}}], 'needs an "alias"'),
    ([{'alias': 'v1'}], '"tags" must map repository names to a tag'),
    ([{'alias': 'v1', 'tags': {}}], '"tags" must map repository names to a tag'),
    ([{'alias': 'v1', 'tags': {'a': ''}}], '"tags" must map repository names to a tag'),
    ([{'alias': 'v1', 'tags': ['a']}], '"tags" must map repository names to a tag'),
    ([{'alias': 'v1', 'tags': {'a': '1', 'A': '2'}}], 'listed twice'),
    ([{'alias': 'v1', 'tags': {'a': '1'}}, {'alias': 'V1', 'tags': {'a': '2'}}], 'alias used twice'),
    ([{'alias': 'v1', 'tags': {'a': '1'}, 'current': True}, {'alias': 'v2', 'tags': {'a': '2'}, 'current': True}], 'more than one set is marked'),
    ([{'alias': 'v1', 'tags': {'a': '1'}, 'current': 'yes'}], '"current" must be true or false'),
    ([{'alias': 'v1', 'tags': {'a': '1'}, 'colour': 'x'}], 'unknown key\\(s\\) colour'),
    ({'alias': 'v1'}, 'must be a list'),
])
def test_invalid_release_sets(bad, msg):
    with pytest.raises(ConfigError, match=msg):
        n(release_sets=bad)

def test_shipped_config_follows_the_new_shape():
    c = config.load('config/repos.json')
    assert [s['type'] for s in c['sources']] == ['query'] and all('fallback' not in s for s in c['sources'])
    assert [r['name'] for r in c['repositories']] == ['infra-automation']
    assert 'engineering-tracker' in c['exclude'] and c['security']['workflow'] == 'security.yml'

def test_license_labels_default_and_can_be_renamed_one_at_a_time():
    assert n()['licenses']['labels'] == {'green': 'Preferred', 'yellow': 'Not recommended', 'red': 'Not to use'}
    assert n(licenses={'labels': {'red': ' Avoid '}})['licenses']['labels'] == {'green': 'Preferred', 'yellow': 'Not recommended', 'red': 'Avoid'}

def test_dependency_settings_default_to_everything_on():
    d = n()['dependencies']
    assert all(d['checks'].values()) and d['images']['workers'] == 4 and d['groups']['aliases']['tests'] == 'test'
    assert d['terraform']['trusted_registries'] == ['registry.terraform.io', 'registry.opentofu.org'] and d['ecosystem_names']['golang'] == 'Go'

def test_dependency_settings_override_one_key_at_a_time():
    d = n(dependencies={'checks': {'images': False}, 'images': {'workers': 2}, 'groups': {'aliases': {'Specs': 'test'}},
                        'ecosystem_names': {'golang': 'Go Modules'}})['dependencies']
    assert d['checks']['images'] is False and d['checks']['actions'] is True and d['images']['workers'] == 2 and d['images']['scan_timeout'] == 900
    assert d['groups']['aliases'] == {'specs': 'test'}   # a map given replaces the default, keys compared in lower case
    assert d['ecosystem_names']['golang'] == 'Go Modules' and d['ecosystem_names']['npm'] == 'npm'   # names are merged over the defaults

@pytest.mark.parametrize('bad,msg', [
    ({'scan': True}, 'unknown key'),
    ({'checks': {'images': 'no'}}, 'checks.images must be true or false'),
    ({'checks': {'trivy': True}}, 'unknown key'),
    ({'images': {'workers': 0}}, 'workers must be a whole number from 1 to 16'),
    ({'images': {'scan_timeout': True}}, 'scan_timeout must be a whole number'),
    ({'groups': {'aliases': {'tests': ''}}}, 'groups.aliases must map names'),
    ({'groups': {'default_workflow_group': ''}}, 'default_workflow_group'),
    ({'terraform': {'trusted_registries': 'registry.terraform.io'}}, 'must be a list'),
    ({'license_aliases': ['MIT']}, 'license_aliases must map'),
])
def test_invalid_dependency_settings(bad, msg):
    with pytest.raises(ConfigError, match=msg):
        n(dependencies=bad)

def test_the_shipped_config_loads():
    assert config.load('config/repos.json')['dependencies']['checks']['images'] is True

def test_image_sources_and_licenses():
    d = n(dependencies={'image_sources': {'jaegertracing/all-in-one': 'jaegertracing/jaeger'}, 'image_licenses': {'postgres': 'PostgreSQL'}})['dependencies']
    assert d['image_sources'] == {'jaegertracing/all-in-one': 'jaegertracing/jaeger'} and d['image_licenses'] == {'postgres': 'PostgreSQL'}
    assert n()['dependencies']['image_sources'] == {} and n()['dependencies']['image_licenses'] == {}
    with pytest.raises(ConfigError, match='owner/repo'):
        n(dependencies={'image_sources': {'postgres': 'https://github.com/postgres/postgres'}})
    with pytest.raises(ConfigError, match='owner/repo'):
        n(dependencies={'image_sources': {'postgres': 'postgres/..'}})
