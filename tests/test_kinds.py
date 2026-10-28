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

def test_images_are_classed_by_what_they_are():
    assert [image_kind(n) for n in ('postgres', 'docker.io/postgres', 'redis', 'grafana/loki', 'jaegertracing/all-in-one',
            'docker.langfuse.com/langfuse/langfuse', 'cgr.dev/chainguard/minio', 'temporalio/ui', 'ghcr.io/openagrinet/knowledge-provider')] == \
        ['Database', 'Database', 'Cache', 'Observability', 'Observability', 'Observability', 'Object storage', 'Workflow', 'Application']

def test_only_images_get_a_kind():
    deps = [{'ecosystem': 'docker', 'name': 'redis'}, {'ecosystem': 'npm', 'name': 'redis'}]
    add_kinds(deps)
    assert deps[0]['kind'] == 'Cache' and 'kind' not in deps[1]

def test_kinds_come_from_the_config(configured):
    configured(image_kinds={'Onix': 'Network adapter'}, default_image_kind='Service')
    assert image_kind('fidedocker/onix-adapter') == 'Network adapter' and image_kind('postgres') == 'Service'
    with pytest.raises(config.ConfigError, match='default_image_kind'):
        config.dependency_settings({'default_image_kind': ''})
