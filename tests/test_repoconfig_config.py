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
    assert c['repositories'][0] == {'name': 'a', 'branch': None, 'tags': [], 'security_workflow': None}
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
