import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.rules.reasons import explain, short_error
from stackinfo.lookups import stars

def why(d):
    explain([d])
    return {k: (v['state'], v['why']) for k, v in d.get('missing', {}).items()}

def test_filled_dependencies_have_no_missing():
    d = {'ecosystem': 'npm', 'name': 'react', 'version': '18.3.1', 'latest': '19.0.0', 'license': 'MIT', 'vulns': {'count': 0}}
    assert why(d) == {} and 'missing' not in d

def test_local_actions_are_not_applicable():
    got = why({'ecosystem': 'githubAction', 'name': './.github/actions/x', 'version': 'latest', 'latest': None, 'license': None, 'vulns': None})
    assert {k: s for k, (s, _) in got.items()} == {'latest': 'na', 'license': 'na', 'vulns': 'na'}

def test_package_not_on_the_registry():
    got = why({'ecosystem': 'python', 'name': 'en-core-web-sm', 'version': 'latest', 'latest': None, 'license': None, 'license_of': 'not found', 'vulns': None})
    assert got['latest'][0] == 'nil' and 'Not published on PyPI' in got['latest'][1]
    assert 'no source repository' in got['license'][1] and 'no version' in got['vulns'][1].lower()

def test_lookup_errors_are_named():
    d = {'ecosystem': 'docker', 'name': 'minio/minio', 'version': 'latest', 'latest': None, 'latest_of': 'floating', 'vulns': None,
         'errors': {'latest': '401 Unauthorized', 'vulns': 'failed to pull container image', 'license': 'failed to pull container image'}}
    got = why(d)
    assert got['latest'] == ('nil', 'Registry lookup failed: 401 Unauthorized') and got['vulns'] == ('nil', 'Scan failed: failed to pull container image')
    assert 'could not be read' in got['license'][1] and 'errors' not in d

def test_images_without_labels_and_unmatched_floating_tags():
    got = why({'ecosystem': 'docker', 'name': 'postgres', 'version': 'latest', 'latest': None, 'latest_of': 'floating', 'license': None, 'vulns': {'count': 3}})
    assert got['license'][0] == 'nil' and got['license'][1].startswith('No license found') and 'none of the newest 30' in got['latest'][1] and 'vulns' not in got

def test_unresolved_variable_tags():
    got = why({'ecosystem': 'docker', 'name': 'app', 'version': '${TAG', 'latest': None, 'license': None, 'vulns': None})
    assert 'unresolved ${VAR}' in got['latest'][1] and 'unresolved ${VAR}' in got['vulns'][1]

def test_action_pinned_to_a_branch():
    got = why({'ecosystem': 'githubAction', 'name': 'x/y', 'version': 'main', 'latest': 'v2', 'license': 'MIT', 'vulns': None})
    assert got == {'vulns': ('nil', 'Pinned to a branch or to a commit no release tag points at, so no version to check')}

def test_short_error_hides_tokens():
    assert short_error(RuntimeError('first\n401 for url with token=abc123 here')) == '401 for url with token [hidden] here'

def test_license_from_the_source_repo_when_the_registry_has_none():
    deps = [{'ecosystem': 'golang', 'name': 'github.com/pgvector/pgvector-go/pgx', 'license': None},
            {'ecosystem': 'npm', 'name': 'x', 'license': None, 'license_of': 'error'},
            {'ecosystem': 'npm', 'name': 'y', 'license': 'MIT'}]
    stars.fill_licenses(deps, license_of=lambda repo: {'pgvector/pgvector-go': 'MIT'}.get(repo))
    assert deps[0]['license'] == 'MIT' and deps[0]['license_of'] == 'source'
    assert deps[1]['license'] is None and deps[2]['license'] == 'MIT' and 'license_of' not in deps[2]

def kinds(d):
    explain([d])
    return d['missing']['license']['kind']

def test_only_a_license_nothing_states_counts_as_no_license():
    assert kinds({'ecosystem': 'npm', 'name': 'x', 'version': '1', 'license': None, 'latest': '1', 'vulns': {'count': 0}}) == 'none'
    assert kinds({'ecosystem': 'python', 'name': 'en-core-web-sm', 'version': 'latest', 'license': None, 'license_of': 'not found', 'vulns': None}) == 'none'
    assert kinds({'ecosystem': 'docker', 'name': 'redis', 'version': '7', 'license': None, 'vulns': {'count': 0}}) == 'none'
    assert kinds({'ecosystem': 'npm', 'name': 'x', 'version': '1', 'license': None, 'license_of': 'error', 'vulns': None}) == 'error'
    assert kinds({'ecosystem': 'docker', 'name': 'a/b', 'version': '1', 'license': None, 'vulns': None, 'errors': {'license': 'denied'}}) == 'error'
    assert kinds({'ecosystem': 'githubAction', 'name': './.github/actions/x', 'version': 'latest', 'license': None, 'vulns': None}) == 'na'
