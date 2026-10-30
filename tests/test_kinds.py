import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from repoconfig import config
from stackinfo import settings
from stackinfo.rules.kinds import image_kind, add_kinds

@pytest.fixture
def configured():
    def apply(**block):
        settings.configure(config.dependency_settings(block))
    yield apply
    settings.reset()   # back to config/dependencies.json

def test_the_kind_is_docker_hubs_first_category_else_the_first_github_topic():
    assert image_kind(['Security', 'Monitoring & observability'], ['grafana']) == ('Security', 'docker hub')   # shown as Docker Hub gives it
    assert image_kind([], ['amazon-s3', 'objectstorage']) == ('amazon-s3', 'github topic')
    assert image_kind([], []) == ('Container', None)

def test_only_images_get_a_kind_and_each_name_is_asked_once():
    asked = []
    hub = lambda n: asked.append(n) or (['Databases & storage'] if n == 'postgres' else [])
    deps = [{'ecosystem': 'docker', 'name': 'postgres'}, {'ecosystem': 'npm', 'name': 'postgres'}, {'ecosystem': 'docker', 'name': 'postgres'},
            {'ecosystem': 'docker', 'name': 'ghcr.io/o/keycloak', 'project': 'github.com/keycloak/keycloak'}]
    add_kinds(deps, hub=hub, topics=lambda r: ['oidc'] if r == 'keycloak/keycloak' else [], cache={})
    assert asked == ['postgres', 'ghcr.io/o/keycloak']
    assert (deps[0]['kind'], deps[0]['kind_of']) == ('Databases & storage', 'docker hub') and 'kind' not in deps[1]
    assert (deps[3]['kind'], deps[3]['kind_of']) == ('oidc', 'github topic')

def test_a_failed_lookup_is_no_category():
    deps = [{'ecosystem': 'docker', 'name': 'redis'}]
    add_kinds(deps, hub=lambda n: 1 / 0, topics=lambda r: [], cache={}, log=lambda m: None)
    assert deps[0]['kind'] == 'Container' and 'kind_of' not in deps[0]

def test_the_default_comes_from_the_config(configured):
    configured(default_image_kind='Service')
    assert image_kind([], [])[0] == 'Service'
    with pytest.raises(config.ConfigError, match='unknown key'):   # no hand-made names for categories or images
        config.dependency_settings({'image_kind_aliases': {'x': 'y'}})
    with pytest.raises(config.ConfigError, match='default_image_kind'):
        config.dependency_settings({'default_image_kind': ''})
