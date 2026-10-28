import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import terraform as tf, stars

class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status
    def json(self):
        return self.body
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

def test_parse_provider_addresses():
    assert tf.parse('registry.opentofu.org/hashicorp/aws') == ('registry.opentofu.org', 'hashicorp', 'aws')
    assert tf.parse('hashicorp/tls') == ('registry.opentofu.org', 'hashicorp', 'tls')
    assert tf.parse('evil/../x') is None and tf.parse('aws_s3_bucket') is None

def test_latest_and_source_repository():
    asked = []
    def get(url):
        asked.append(url)
        return Resp({'versions': [{'version': '6.62.0'}, {'version': '6.70.0'}, {'version': '7.0.0-beta1'}, {'version': '6.9.0'}]})
    deps = [{'ecosystem': 'terraform', 'name': 'registry.opentofu.org/hashicorp/aws', 'version': '6.62.0'},
            {'ecosystem': 'terraform', 'name': 'registry.opentofu.org/hashicorp/aws', 'version': '6.62.0'}, {'ecosystem': 'npm', 'name': 'x'}]
    tf.annotate(deps, get=get, cache={})
    assert deps[0]['latest'] == '6.70.0' and deps[0]['project'] == 'github.com/hashicorp/terraform-provider-aws'
    assert asked == ['https://registry.opentofu.org/v1/providers/hashicorp/aws/versions'] and 'project' not in deps[2]
    assert stars.source_repo(deps[0]) == 'hashicorp/terraform-provider-aws'

def test_registry_failure_is_recorded():
    def get(url):
        return Resp({}, 404)
    deps = [{'ecosystem': 'terraform', 'name': 'hashicorp/gone', 'version': '1.0.0'}]
    tf.annotate(deps, get=get, cache={}, log=lambda m: None)
    assert 'latest' not in deps[0] and 'HTTP 404' in deps[0]['errors']['latest']
