import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from repoconfig.config import RELEASE_DEFAULTS as R
from releasefind.versions import parse

@pytest.mark.parametrize('kind,name,version', [
    ('branch', 'release-0.2.0', '0.2.0'), ('tag', 'v0.1.0', '0.1.0'), ('tag', '0.1.0', '0.1.0'),
    ('tag', 'v0.0.1-RC1', '0.0.1-RC1'), ('tag', '1.2', '1.2'), ('branch', 'release-v3.0.0-rc.2', '3.0.0-rc.2'),
])
def test_parse_accepts_version_names(kind, name, version):
    assert parse(kind, name, R)['version'] == version

@pytest.mark.parametrize('kind,name', [
    ('branch', 'release-notes'), ('branch', 'hotfix-0.2.0'), ('branch', 'v0.2.0'), ('tag', 'fork-point'), ('tag', 'release-0.1.0'), ('tag', 'v1.x'), ('tag', ''),
])
def test_parse_ignores_names_that_are_not_versions(kind, name):
    assert parse(kind, name, R) is None

def test_v_prefix_and_trailing_zeros_are_one_version():
    assert parse('tag', 'v1.2', R)['identity'] == parse('tag', '1.2.0', R)['identity']
    assert parse('tag', 'v1.2.0-RC1', R)['identity'] == parse('tag', '1.2.0-rc1', R)['identity']

def test_ordering_numeric_not_text_and_prerelease_below_final():
    order = ['0.0.9', '0.0.10', '0.1.0-RC1', '0.1.0-RC2', '0.1.0-beta', '0.1.0']
    names = ['v0.1.0', 'v0.1.0-RC2', 'v0.0.9', 'v0.1.0-beta', 'v0.0.10', 'v0.1.0-RC1']
    got = sorted(names, key=lambda n: parse('tag', n, R)['sort'])
    assert [parse('tag', n, R)['version'] for n in got] == ['0.0.9', '0.0.10', '0.1.0-beta', '0.1.0-RC1', '0.1.0-RC2', '0.1.0']

def test_custom_tag_pattern_and_branch_prefix():
    rc = {**R, 'tag_pattern': r'^rel/(?P<version>\d+\.\d+\.\d+)$', 'branch_prefix': 'rel/'}
    assert parse('tag', 'rel/2.0.1', rc)['version'] == '2.0.1'
    assert parse('tag', 'v2.0.1', rc) is None
    assert parse('branch', 'rel/2.0.1', rc)['version'] == '2.0.1'
