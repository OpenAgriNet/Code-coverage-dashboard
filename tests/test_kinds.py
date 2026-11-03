import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from repoconfig import config
from stackinfo.rules.kinds import add_kinds

def test_the_kind_is_docker_hubs_first_category_and_only_images_are_asked_once():
    asked = []
    hub = lambda n: asked.append(n) or (['Databases & storage', 'Monitoring & observability'] if n == 'postgres' else [])
    deps = [{'ecosystem': 'docker', 'name': 'postgres'}, {'ecosystem': 'npm', 'name': 'postgres'}, {'ecosystem': 'docker', 'name': 'postgres'},
            {'ecosystem': 'docker', 'name': 'ghcr.io/o/keycloak', 'project': 'github.com/keycloak/keycloak'}]
    add_kinds(deps, hub=hub, cache={})
    assert asked == ['postgres', 'ghcr.io/o/keycloak']
    assert deps[0]['kind'] == 'Databases & storage' and deps[2]['kind'] == 'Databases & storage'   # shown as Docker Hub gives it
    assert 'kind' not in deps[1] and 'kind' not in deps[3]   # no category: no kind, nothing guessed

def test_a_failed_lookup_is_no_category():
    deps = [{'ecosystem': 'docker', 'name': 'redis'}]
    add_kinds(deps, hub=lambda n: 1 / 0, cache={}, log=lambda m: None)
    assert 'kind' not in deps[0]

def test_no_hand_made_names_for_kinds_or_ecosystems():
    for key in ('image_kind_aliases', 'default_image_kind', 'ecosystem_names'):
        with pytest.raises(config.ConfigError, match='unknown key'):
            config.dependency_settings({key: 'x'})
