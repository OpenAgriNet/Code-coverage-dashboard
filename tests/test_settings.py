import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from repoconfig import config
from stackinfo import settings, record as r
from stackinfo.rules.reasons import explain
from stackinfo.sources import analyser, manifests, tools
from stackinfo.lookups import imagescan, terraform

@pytest.fixture
def configured():
    """Apply a "dependencies" block for one test, then go back to the defaults."""
    def apply(**block):
        settings.configure(config.dependency_settings(block))
    yield apply
    settings.configure(config.dependency_settings(None))

def test_defaults_apply_until_configured():
    assert settings.check('images') and settings.get('images', 'workers') == 4

def test_a_check_turned_off_is_skipped_and_explained(configured, monkeypatch):
    configured(checks={'images': False, 'vulnerabilities': False})
    monkeypatch.setattr(r, 'repo_license', lambda repo: None)
    monkeypatch.setattr(r, 'repo_stars', lambda repo: None)
    called = []
    raw = {'dependencies': [['docker', 'postgres', '17'], ['npm', 'react', '18.3.1']]}
    rec = r.stack_record({'name': 'na', 'branch': 'main'}, analyse=lambda repo, branch: raw,
                         info=lambda e, n, v: {'ecosystem': e, 'name': n, 'version': v, 'latest': '19.0.0' if e == 'npm' else None, 'license': 'MIT' if e == 'npm' else None},
                         vulns=lambda d: called.append('osv'), actions=lambda d: called.append('actions'), images=lambda d: called.append('images'),
                         stars=lambda d: None, licenses=lambda d: None, providers=lambda d: None, tools=lambda d: None)
    assert called == ['actions']
    by = {d['name']: d for d in rec['dependencies']}
    assert by['postgres']['missing']['vulns']['why'] == 'Not looked up: dependencies.checks.images is turned off in config/repos.json'
    assert by['react']['missing']['vulns']['why'].endswith('dependencies.checks.vulnerabilities is turned off in config/repos.json')

def test_workflow_tools_can_be_left_out(configured, tmp_path):
    (tmp_path / '.github' / 'workflows').mkdir(parents=True)
    (tmp_path / '.github' / 'workflows' / 'security.yml').write_text('run: pip install bandit\n')
    assert ('python', 'bandit') in analyser.read_manifests(str(tmp_path))
    configured(checks={'workflow_tools': False})
    assert ('python', 'bandit') not in analyser.read_manifests(str(tmp_path))

def test_group_names_and_workflow_purposes_come_from_the_config(configured):
    configured(groups={'aliases': {'specs': 'test'}, 'workflow_purposes': {'nightly': 'security'}, 'default_workflow_group': 'automation'})
    assert manifests.group_name('Specs') == 'test' and manifests.group_name('tests') == 'tests'   # the given map replaces the default
    assert tools.purpose('nightly-scan.yml') == 'security' and tools.purpose('security.yml') == 'automation'

def test_image_limits_and_license_aliases_come_from_the_config(configured):
    configured(images={'max_findings': 1}, license_aliases={'the apache license': 'Apache-2.0'})
    items = [{'id': str(n), 'severity': 'HIGH', 'fixed': None, 'summary': str(n)} for n in range(3)]
    assert len(imagescan.summarize(items)['items']) == 1 and imagescan.summarize(items)['count'] == 3
    assert imagescan.image_license({'org.opencontainers.image.licenses': 'The Apache License'}, lambda r: None) == ('Apache-2.0', 'label')

def test_trusted_terraform_registries_come_from_the_config(configured):
    configured(terraform={'trusted_registries': ['registry.example.com']})
    deps = [{'ecosystem': 'terraform', 'name': 'registry.example.com/acme/thing', 'version': '1.0.0'}]
    class Resp:
        status_code = 200
        def json(self): return {'versions': [{'version': '1.0.0'}]}
        def raise_for_status(self): pass
    terraform.annotate(deps, get=lambda url: Resp(), cache={})
    assert deps[0]['project'] == 'github.com/acme/terraform-provider-thing'
