import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.lookups import stars as s

def test_source_repo_per_ecosystem():
    assert s.source_repo({'ecosystem': 'githubAction', 'name': 'github/codeql-action/init'}) == 'github/codeql-action'
    assert s.source_repo({'ecosystem': 'githubAction', 'name': './.github/actions/x'}) is None
    assert s.source_repo({'ecosystem': 'golang', 'name': 'github.com/jackc/pgx/v5'}) == 'jackc/pgx'
    assert s.source_repo({'ecosystem': 'golang', 'name': 'golang.org/x/tools'}) == 'golang/tools'   # golang.org/x is mirrored on GitHub
    assert s.source_repo({'ecosystem': 'npm', 'name': 'react', 'project': 'github.com/facebook/react'}) == 'facebook/react'
    assert s.source_repo({'ecosystem': 'python', 'name': 'x', 'project': 'gitlab.com/a/b'}) is None
    assert s.source_repo({'ecosystem': 'npm', 'name': 'x', 'project': 'github.com/../evil'}) is None

def test_annotate_github_and_docker_hub_stars_once_each():
    calls = []
    def api(repo):
        calls.append(repo)
        return {'facebook/react': 230000, 'actions/cache': 4800}.get(repo)
    hub_calls = []
    def hub(name):
        hub_calls.append(name)
        return 15045 if name == 'postgres' else None
    deps = [{'ecosystem': 'npm', 'name': 'react', 'project': 'github.com/facebook/react'},
            {'ecosystem': 'npm', 'name': 'react-dom', 'project': 'github.com/facebook/react'},
            {'ecosystem': 'githubAction', 'name': 'actions/cache'},
            {'ecosystem': 'docker', 'name': 'postgres'}, {'ecosystem': 'docker', 'name': 'ghcr.io/o/app'},
            {'ecosystem': 'golang', 'name': 'golang.org/x/tools'}]
    s.annotate(deps, api=api, hub=hub, cache={})
    assert [d.get('stars') for d in deps] == [230000, 230000, 4800, 15045, None, None]
    assert deps[0]['stars_of'] == 'github.com/facebook/react' and deps[3]['stars_of'] == 'hub.docker.com/_/postgres'
    assert calls.count('facebook/react') == 1 and hub_calls == ['postgres']

def test_failed_lookups_leave_no_stars():
    def boom(path):
        raise RuntimeError('rate limited')
    deps = [{'ecosystem': 'githubAction', 'name': 'x/y'}]
    logs = []
    s.annotate(deps, api=boom, hub=boom, cache={}, log=logs.append)
    assert 'stars' not in deps[0] and logs

def test_hub_stars_only_for_docker_hub_images():
    got = []
    def get(url):
        got.append(url)
        class R:
            status_code = 200
            def json(self):
                return {'star_count': 7}
        return R()
    assert s.hub_stars('grafana/loki', get=get) == 7 and s.hub_stars('ghcr.io/o/app', get=get) is None
    assert s.hub_stars('postgres', get=get) == 7
    assert got == ['https://hub.docker.com/v2/repositories/grafana/loki/', 'https://hub.docker.com/v2/repositories/library/postgres/']

def test_only_whole_numbers_become_stars():
    deps = [{'ecosystem': 'githubAction', 'name': 'a/b'}, {'ecosystem': 'githubAction', 'name': 'c/d'}, {'ecosystem': 'githubAction', 'name': 'e/f'}]
    answers = {'a/b': '<img src=x onerror=alert(1)>', 'c/d': -5, 'e/f': 7}
    s.annotate(deps, api=lambda repo: answers[repo], cache={})
    assert [d.get('stars') for d in deps] == [None, None, 7]

def test_an_image_with_a_known_repository_counts_its_github_stars():
    deps = [{'ecosystem': 'docker', 'name': 'docker.langfuse.com/langfuse/langfuse', 'project': 'github.com/langfuse/langfuse'},
            {'ecosystem': 'docker', 'name': 'postgres'}, {'ecosystem': 'docker', 'name': 'cgr.dev/chainguard/minio'}]
    hub_asked = []
    def hub(name):
        hub_asked.append(name)
        return 15045
    s.annotate(deps, api=lambda repo: {'langfuse/langfuse': 26000}.get(repo), hub=hub, cache={})
    assert deps[0]['stars'] == 26000 and deps[0]['stars_of'] == 'github.com/langfuse/langfuse'
    assert deps[1]['stars'] == 15045 and hub_asked == ['postgres']   # no repository known: Docker Hub
    assert 'stars' not in deps[2]                                     # neither: nothing

def test_a_failed_license_lookup_is_not_no_license():
    from stackinfo.rules.reasons import explain
    def boom(repo):
        raise RuntimeError('deps.dev down')
    deps = [{'ecosystem': 'githubRelease', 'name': 'x/tool', 'project': 'github.com/x/tool', 'license': None, 'latest': 'v1', 'vulns': {'count': 0}}]
    s.fill_licenses(deps, license_of=boom)
    explain(deps)
    assert deps[0]['missing']['license']['kind'] == 'error' and 'deps.dev down' in deps[0]['missing']['license']['why']

def test_go_modules_off_github_take_their_repository_from_deps_dev_or_the_host_rules():
    assert s.source_repo({'ecosystem': 'golang', 'name': 'go.opentelemetry.io/otel', 'project': 'github.com/open-telemetry/opentelemetry-go'}) == 'open-telemetry/opentelemetry-go'
    assert s.source_repo({'ecosystem': 'golang', 'name': 'golang.org/x/crypto'}) == 'golang/crypto'
    assert s.source_repo({'ecosystem': 'golang', 'name': 'golang.org/x/vuln/cmd/govulncheck'}) == 'golang/vuln'
    assert s.source_repo({'ecosystem': 'golang', 'name': 'gopkg.in/yaml.v3'}) == 'go-yaml/yaml'
    assert s.source_repo({'ecosystem': 'golang', 'name': 'gopkg.in/natefinch/lumberjack.v2'}) == 'natefinch/lumberjack'
    assert s.source_repo({'ecosystem': 'golang', 'name': 'github.com/jackc/pgx/v5', 'project': 'github.com/other/repo'}) == 'jackc/pgx'   # the module path wins
    assert s.source_repo({'ecosystem': 'golang', 'name': 'k8s.io/client-go'}) is None

def test_a_sponsors_page_is_not_a_source_repository():
    assert s.source_repo({'ecosystem': 'python', 'name': 'uvicorn', 'project': 'github.com/sponsors/encode'}) is None

def test_ghcr_images_take_the_repository_of_the_same_name():
    from stackinfo.lookups import images as im
    assert im.image_repo('ghcr.io/openagrinet/knowledge-provider', None, None) == 'openagrinet/knowledge-provider'
    assert im.image_repo('docker.io/library/redis', None, None) is None

def test_a_non_standard_license_gets_a_second_opinion_from_the_source_repository():
    deps = [{'ecosystem': 'python', 'name': 'huggingface-hub', 'project': 'github.com/huggingface/huggingface_hub', 'license': 'non-standard'},
            {'ecosystem': 'python', 'name': 'pypdf', 'project': 'github.com/py-pdf/pypdf', 'license': 'non-standard'},
            {'ecosystem': 'python', 'name': 'fastapi', 'project': 'github.com/fastapi/fastapi', 'license': 'MIT'}]
    asked = []
    def repo_license(repo):
        asked.append(repo)
        return {'huggingface/huggingface_hub': 'Apache-2.0'}.get(repo)   # pypdf: GitHub cannot name it either
    s.fill_licenses(deps, license_of=repo_license, pypi=lambda name: {'pypdf': 'BSD-3-Clause'}.get(name))
    assert deps[0]['license'] == 'Apache-2.0' and deps[0]['license_of'] == 'github'
    assert deps[1]['license'] == 'BSD-3-Clause' and deps[1]['license_of'] == 'pypi'   # GitHub cannot name it; PyPI can
    assert asked == ['huggingface/huggingface_hub', 'py-pdf/pypdf']   # a license deps.dev did name is left alone

def test_pypi_license_reads_the_spdx_expression_else_an_aliased_text_or_classifier(monkeypatch):
    monkeypatch.setattr(s.settings, 'get', lambda k: {'lgpl with exceptions': 'LGPL'})
    class R:
        status_code = 200
        def __init__(self, info): self.info = info
        def raise_for_status(self): pass
        def json(self): return {'info': self.info}
    assert s.pypi_license('pypdf', get=lambda u, timeout: R({'license_expression': 'BSD-3-Clause'})) == 'BSD-3-Clause'
    assert s.pypi_license('psycopg2', get=lambda u, timeout: R({'license': 'LGPL with exceptions'})) == 'LGPL'
    assert s.pypi_license('x', get=lambda u, timeout: R({'license': 'see LICENSE', 'classifiers': ['License :: Other/Proprietary License']})) is None

def test_a_package_installed_from_a_wheel_url_takes_the_wheels_license():
    url = 'https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl'
    deps = [{'ecosystem': 'python', 'name': 'en-core-web-sm', 'license': None, 'license_of': 'not found', 'url': url}]
    s.fill_licenses(deps, license_of=lambda repo: None, wheel=lambda u: 'MIT' if u == url else None)
    assert deps[0]['license'] == 'MIT' and deps[0]['license_of'] == 'wheel'
