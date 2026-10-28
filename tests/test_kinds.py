import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from repoconfig import config
from stackinfo import settings
from stackinfo.rules.kinds import image_vendor, add_vendors

@pytest.fixture
def configured():
    def apply(**block):
        settings.configure(config.dependency_settings(block))
    yield apply
    settings.reset()   # back to config/dependencies.json

def test_an_image_is_its_vendor_read_from_its_name():
    assert [image_vendor(n) for n in ('redis', 'docker.io/postgres', 'grafana/loki', 'docker.langfuse.com/langfuse/langfuse-worker',
            'cgr.dev/chainguard/minio', 'ghcr.io/openagrinet/knowledge-provider', 'experience-ui')] == \
        ['redis', 'postgres', 'grafana', 'langfuse', 'chainguard', 'openagrinet', 'experience-ui']

def test_a_few_vendors_have_aliases_in_the_config():
    assert [image_vendor(n) for n in ('prom/prometheus', 'temporalio/ui', 'jaegertracing/all-in-one', 'fidedocker/onix-adapter')] == \
        ['prometheus', 'temporal', 'jaeger', 'beckn']

def test_only_images_get_a_vendor(configured):
    configured(image_vendor_aliases={'Grafana': 'Grafana Labs'})
    deps = [{'ecosystem': 'docker', 'name': 'grafana/loki'}, {'ecosystem': 'npm', 'name': 'redis'}]
    add_vendors(deps)
    assert deps[0]['vendor'] == 'Grafana Labs' and 'vendor' not in deps[1]
