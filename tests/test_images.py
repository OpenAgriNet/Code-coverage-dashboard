import json, os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from common import safehttp as sh
from stackinfo import settings
from stackinfo.lookups import images as im, imagescan as sc, projects as pj, registry as rg

def test_split_names_registry_and_repository_path():
    assert rg.split('postgres') == ('registry-1.docker.io', 'library/postgres')
    assert rg.split('docker.io/postgres') == ('registry-1.docker.io', 'library/postgres')
    assert rg.split('grafana/loki') == ('registry-1.docker.io', 'grafana/loki')
    assert rg.split('docker.langfuse.com/langfuse/langfuse') == ('docker.langfuse.com', 'langfuse/langfuse')
    assert rg.split('localhost:5000/app') == ('localhost:5000', 'app')

def test_latest_keeps_the_shape_of_the_current_tag():
    assert rg.latest_like('17', ['16', '17', '18', '18-alpine', '17.2', 'latest', '9']) == '18'
    assert rg.latest_like('1.37', ['1.36', '1.37', '1.38', '1.38-musl', '1.4', 'latest']) == '1.38'
    assert rg.latest_like('25.7-alpine', ['25.7-alpine', '25.12-alpine', '25.12', '26.1']) == '25.12-alpine'
    assert rg.latest_like('0.8.0-pg16', ['0.8.0-pg16', '0.8.1-pg16', '0.9.0-pg17']) == '0.8.1-pg16'
    assert rg.latest_like('v2.0.0', ['v2.0.0', 'v2.1.0', '2.2.0']) == 'v2.1.0'

def test_floating_tags_have_no_latest():
    assert rg.latest_like('latest', ['latest', '1.0']) is None
    assert rg.latest_like('alpine', ['alpine', '3.20']) is None

class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
    def json(self):
        return self._body
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')
    def close(self):
        pass

def test_tags_gets_an_anonymous_token_then_follows_pages():
    calls = []
    def get(url, headers=None, params=None):
        calls.append((url, headers, params))
        if url.startswith('https://auth.example/token'):
            assert params == {'service': 'reg', 'scope': 'repository:a/b:pull'}
            return Resp(200, {'token': 'anon'})
        if not headers:
            return Resp(401, headers={'WWW-Authenticate': 'Bearer realm="https://auth.example/token",service="reg",scope="repository:a/b:pull"'})
        if url.endswith('n=1000'):
            return Resp(200, {'tags': ['1']}, {'Link': '</v2/a/b/tags/list?n=1000&last=1>; rel="next"'})
        return Resp(200, {'tags': ['2']})
    assert rg.tags('reg.example', 'a/b', get=get, is_public=lambda h: True) == ['1', '2']
    assert calls[-1][0] == 'https://reg.example/v2/a/b/tags/list?n=1000&last=1' and calls[-1][1] == {'Authorization': 'Bearer anon'}

def test_tags_refuses_a_non_https_token_realm():
    def get(url, headers=None, params=None):
        return Resp(401, headers={'WWW-Authenticate': 'Bearer realm="http://evil/token",service="x"'})
    try:
        rg.tags('reg.example', 'a/b', get=get, is_public=lambda h: True)
        assert False
    except RuntimeError as e:
        assert 'realm' in str(e)

SCAN = {'results': [{'source': {'path': '/lib/apk/db/installed', 'type': 'os'}, 'packages': [
    {'package': {'name': 'glibc', 'version': '2.44-r10', 'ecosystem': 'Wolfi'},
     'groups': [{'ids': ['CGA-1', 'CGA-2'], 'aliases': ['CGA-1', 'CGA-2', 'CVE-2026-1'], 'max_severity': '9.8'},
                {'ids': ['CGA-3'], 'aliases': ['CGA-3'], 'max_severity': ''}],
     'vulnerabilities': [
        {'id': 'CGA-1', 'summary': 'heap overflow', 'affected': [{'package': {'ecosystem': 'Wolfi', 'name': 'glibc'}, 'ranges': [{'type': 'ECOSYSTEM', 'events': [{'introduced': '0'}, {'fixed': '2.44-r11'}]}]}]},
        {'id': 'CGA-2', 'affected': []},
        {'id': 'CGA-3', 'details': 'no fix yet\nmore', 'database_specific': {'severity': 'LOW'}, 'affected': []}]},
    {'package': {'name': 'zlib', 'version': '1.3', 'ecosystem': 'Wolfi'}}]}]}

def test_scan_items_one_per_package_and_advisory_group():
    items = sc.items_of(SCAN)
    assert [(i['id'], i['cve'], i['severity'], i['fixed']) for i in items] == [('CGA-1', 'CVE-2026-1', 'CRITICAL', '2.44-r11'), ('CGA-3', None, 'LOW', None)]
    assert items[0]['summary'] == 'glibc 2.44-r10: heap overflow' and items[1]['summary'] == 'glibc 2.44-r10: no fix yet'

def test_scan_runs_osv_scanner_without_secrets(monkeypatch):
    monkeypatch.setenv('GH_TOKEN', 'secret')
    seen = {}
    def run(cmd, **kw):
        seen.update(cmd=cmd, env=kw['env'])
        class P: returncode = 1; stdout = json.dumps(SCAN); stderr = ''
        return P()
    got = sc.scan('postgres:17', run=run, binary='/bin/osv', docker=None)
    assert seen['cmd'] == ['/bin/osv', 'scan', 'image', '--all-packages', '--licenses=MIT', '--format', 'json', 'postgres:17'] and 'secret' not in seen['env'].values()
    assert got['count'] == 2 and got['severity'] == 'CRITICAL' and got['fixed_in'] is None and got['fixable'] == 1 and got['unfixed'] == 1

def test_scan_error_exit_raises():
    def run(cmd, **kw):
        class P: returncode = 127; stdout = ''; stderr = 'pull access denied'
        return P()
    try:
        sc.scan('private/app:1', run=run, binary='/bin/osv', docker=None)
        assert False
    except RuntimeError as e:
        assert 'pull access denied' in str(e)

def test_annotate_fills_images_and_skips_unresolved_tags():
    deps = [{'ecosystem': 'docker', 'name': 'postgres', 'version': '17', 'latest': None, 'vulns': None},
            {'ecosystem': 'docker', 'name': 'app', 'version': '${TAG', 'latest': None, 'vulns': None},
            {'ecosystem': 'docker', 'name': 'redis', 'version': 'latest', 'latest': None, 'vulns': None},
            {'ecosystem': 'npm', 'name': 'x', 'version': '1', 'vulns': {'count': 0}}]
    scanned = []
    def scan(ref):
        scanned.append(ref)
        return {'count': 0, 'severity': None, 'fixed_in': None, 'unfixed': 0, 'fixable': 0, 'items': []}
    im.annotate(deps, tags_of=lambda name: ['16', '17', '18', 'latest'], scan=scan, cache={}, is_public=lambda h: True, resolve=lambda n, tag, ts: None)
    assert deps[0]['latest'] == '18' and deps[0]['vulns']['count'] == 0 and deps[0]['vulns']['checked_version'] == '17'
    assert deps[1]['vulns'] is None and deps[1]['latest'] is None
    assert deps[2]['latest'] is None and deps[2]['latest_of'] == 'floating' and deps[2]['vulns'] is not None
    assert sorted(scanned) == ['docker.io/library/postgres:17', 'docker.io/library/redis:latest'] and deps[3]['vulns'] == {'count': 0}

def test_annotate_failures_stay_unchecked():
    deps = [{'ecosystem': 'docker', 'name': 'ghcr.io/o/private', 'version': '1.0', 'latest': None, 'vulns': None}]
    def boom(*a):
        raise RuntimeError('denied')
    logs = []
    im.annotate(deps, tags_of=boom, scan=boom, cache={}, log=logs.append, is_public=lambda h: True)
    assert deps[0]['vulns'] is None and deps[0]['latest'] is None and len(logs) == 2

def test_malformed_image_names_are_not_fetched():
    deps = [{'ecosystem': 'docker', 'name': n, 'version': '1', 'latest': None, 'vulns': None} for n in ('evil.com/../x', 'a b', 'x;rm')]
    im.annotate(deps, tags_of=lambda n: 1 / 0, scan=lambda r: 1 / 0, cache={}, log=lambda m: None, is_public=lambda h: True)
    assert all(d['vulns'] is None and d['latest'] is None for d in deps)

def test_scan_removes_only_images_it_pulled():
    cmds = []
    def run(cmd, **kw):
        cmds.append(cmd)
        class P: returncode = 0 if cmd[1:3] != ['image', 'inspect'] or cmd[-1] == 'have:1' else 1; stdout = '{}'; stderr = ''
        return P()
    sc.scan('new:1', run=run, binary='/bin/osv', docker='/bin/docker')
    sc.scan('have:1', run=run, binary='/bin/osv', docker='/bin/docker')
    assert ['/bin/docker', 'image', 'rm', '-f', 'new:1'] in cmds and ['/bin/docker', 'image', 'rm', '-f', 'have:1'] not in cmds

def test_long_lists_keep_the_worst_items_and_exact_counts(monkeypatch):
    monkeypatch.setitem(settings.CURRENT['images'], 'max_findings', 2)
    items = [{'id': str(n), 'severity': s, 'fixed': f, 'summary': str(n)} for n, (s, f) in enumerate([('LOW', None), ('CRITICAL', None), ('HIGH', '2'), ('CRITICAL', '1')])]
    got = sc.summarize(items)
    assert [i['id'] for i in got['items']] == ['3', '1'] and got['count'] == 4 and got['fixable'] == 2 and got['unfixed'] == 2 and got['severity'] == 'CRITICAL'


def test_images_on_internal_registries_are_never_fetched():
    deps = [{'ecosystem': 'docker', 'name': n, 'version': '1', 'latest': None, 'vulns': None} for n in ('169.254.169.254/x', 'localhost:5000/app')]
    logs = []
    im.annotate(deps, tags_of=lambda n: 1 / 0, scan=lambda r: 1 / 0, cache={}, log=logs.append, is_public=sh.public_host)
    assert all(d['vulns'] is None and d['latest'] is None for d in deps) and len(logs) == 2

def test_token_realm_on_an_internal_host_is_refused():
    def get(url, headers=None, params=None):
        return Resp(401, headers={'WWW-Authenticate': 'Bearer realm="https://169.254.169.254/token",service="x"'})
    try:
        rg.tags('reg.example', 'a/b', get=get, is_public=lambda h: not h.startswith('169.'))
        assert False
    except RuntimeError as e:
        assert 'realm' in str(e)

def test_floating_tag_resolves_to_the_version_with_the_same_digest():
    digests = {'latest': 'sha256:b', '12.3.0': 'sha256:c', '12.2.1': 'sha256:b', '12.2': 'sha256:b'}
    asked = []
    def digest(host, path, ref, auth=None):
        asked.append(ref)
        return digests.get(ref), {'Authorization': 'Bearer t'}
    tags = ['latest', '12.2', '12.2.1', '12.3.0', '12.3.0-ubuntu', 'main', '9.5.0']
    assert rg.version_of('grafana/grafana', 'latest', tags, digest=digest) == '12.2.1'
    assert asked == ['latest', '12.3.0', '12.2.1']

def test_floating_tag_without_a_match_stays_floating():
    def digest(host, path, ref, auth=None):
        return ('sha256:x' if ref == 'latest' else 'sha256:y'), None
    assert rg.version_of('a/b', 'latest', ['1.0.0', '2.0.0'], digest=digest, limit=1) is None

def test_annotate_shows_the_version_behind_latest():
    deps = [{'ecosystem': 'docker', 'name': 'grafana/grafana', 'version': 'latest', 'latest': None, 'vulns': None}]
    im.annotate(deps, tags_of=lambda n: ['12.2.1', '12.3.0'], scan=lambda r: sc.summarize([]), cache={}, is_public=lambda h: True,
                resolve=lambda n, tag, ts: '12.2.1')
    assert deps[0]['resolved'] == '12.2.1' and deps[0]['latest'] == '12.3.0' and deps[0]['latest_of'] == 'registry'

def test_digest_uses_head_and_an_anonymous_token():
    calls = []
    def get(url, headers=None, params=None, method='GET'):
        calls.append((method, url, dict(headers or {})))
        if url.startswith('https://auth.example'):
            return Resp(200, {'token': 'anon'})
        if 'Authorization' not in (headers or {}):
            return Resp(401, headers={'WWW-Authenticate': 'Bearer realm="https://auth.example/token",service="reg"'})
        return Resp(200, headers={'Docker-Content-Digest': 'sha256:abc'})
    d, auth = rg.digest('reg.example', 'a/b', 'latest', get=get, is_public=lambda h: True)
    assert d == 'sha256:abc' and auth == {'Authorization': 'Bearer anon'}
    assert calls[0][0] == 'HEAD' and 'image.index' in calls[0][2]['Accept'] and calls[-1][0] == 'HEAD'

def test_the_same_advisory_on_the_same_package_counts_once():
    pkg = SCAN['results'][0]['packages'][0]
    twice = {'results': [{'packages': [pkg, pkg]}]}
    assert len(sc.items_of(twice)) == 2

def test_image_license_from_label_then_source_repo():
    repo = lambda r: {'grafana/grafana': 'AGPL-3.0'}.get(r)
    assert sc.image_license({'org.opencontainers.image.licenses': 'MIT'}, repo) == ('MIT', 'label')
    assert sc.image_license({'org.opencontainers.image.licenses': 'Apache License 2.0'}, repo) == ('Apache-2.0', 'label')
    assert sc.image_license({'org.opencontainers.image.source': 'https://github.com/grafana/grafana'}, repo) == ('AGPL-3.0', 'source')
    assert sc.image_license({'org.label-schema.vcs-url': 'https://github.com/grafana/grafana.git'}, repo) == ('AGPL-3.0', 'source')
    assert sc.image_license({'org.opencontainers.image.source': 'https://gitlab.com/a/b'}, repo) == (None, None)
    assert sc.image_license({'org.opencontainers.image.source': 'https://github.com/../x'}, repo) == (None, None)
    assert sc.image_license({}, repo) == (None, None)

def test_scan_reads_labels_from_the_pulled_image():
    def run(cmd, **kw):
        class P: returncode = 0; stdout = '{}'; stderr = ''
        if cmd[1:3] == ['image', 'inspect'] and '--format' in cmd:
            P.stdout = '{"org.opencontainers.image.licenses": "MIT"}'
        return P()
    got = sc.scan('a:1', run=run, binary='/bin/osv', docker='/bin/docker')
    assert got['labels'] == {'org.opencontainers.image.licenses': 'MIT'} and got['count'] == 0

def test_annotate_sets_the_image_license():
    deps = [{'ecosystem': 'docker', 'name': 'acme/app', 'version': '1.2.2', 'latest': None, 'vulns': None}]
    scan = lambda ref: {**sc.summarize([]), 'labels': {'org.opencontainers.image.source': 'https://github.com/acme/app'}}
    im.annotate(deps, tags_of=lambda n: ['1.2.2'], scan=scan, cache={}, is_public=lambda h: True, license_of=lambda r: 'AGPL-3.0')
    assert deps[0]['license'] == 'AGPL-3.0' and deps[0]['license_of'] == 'source' and 'labels' not in deps[0]['vulns']

def test_project_license_asks_github_when_deps_dev_cannot_name_it(monkeypatch):
    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {'license': 'non-standard'}
    monkeypatch.setattr(pj.D, 'get', lambda url, timeout=None: R())
    monkeypatch.setattr(pj, 'LICENSES', {})
    monkeypatch.setattr(pj, 'PROJECTS', {})
    asked = []
    def github(path):
        asked.append(path)
        return {'license': {'spdx_id': 'MPL-2.0'}}
    assert pj.project_license('hashicorp/terraform-provider-aws', api=github) == 'MPL-2.0'
    assert asked == ['/repos/hashicorp/terraform-provider-aws/license']

def test_one_image_under_several_spellings_is_scanned_once():
    assert rg.canonical('postgres') == rg.canonical('docker.io/postgres') == rg.canonical('docker.io/library/postgres') == 'docker.io/library/postgres'
    assert rg.canonical('grafana/loki') == 'docker.io/grafana/loki' and rg.canonical('ghcr.io/o/app') == 'ghcr.io/o/app'
    deps = [{'ecosystem': 'docker', 'name': n, 'version': '17', 'latest': None, 'vulns': None} for n in ('postgres', 'docker.io/postgres', 'docker.io/library/postgres')]
    scanned = []
    def scan(ref):
        scanned.append(ref)
        return sc.summarize([])
    im.annotate(deps, tags_of=lambda n: ['17'], scan=scan, cache={}, is_public=lambda h: True, resolve=lambda n, tag, ts: None)
    assert scanned == ['docker.io/library/postgres:17'] and all(d['vulns']['count'] == 0 for d in deps)

def test_tags_that_do_not_fit_in_the_page_limit_raise():
    def get(url, headers=None, params=None):
        return Resp(200, {'tags': ['1']}, {'Link': '</v2/a/b/tags/list?n=1000&last=1>; rel="next"'})
    try:
        rg.tags('reg.example', 'a/b', get=get, pages=3, is_public=lambda h: True)
        assert False
    except RuntimeError as e:
        assert 'more than 3 pages' in str(e)
    def other_host(url, headers=None, params=None):
        return Resp(200, {'tags': ['1']}, {'Link': '<https://evil.example/next>; rel="next"'})
    try:
        rg.tags('reg.example', 'a/b', get=other_host, is_public=lambda h: True)
        assert False
    except RuntimeError as e:
        assert 'another host' in str(e)

def test_build_numbers_and_dates_are_not_the_next_major():
    assert rg.latest_like('17', ['16', '17', '18', '20250101', '1234567']) == '18'
    assert rg.latest_like('9', ['9', '10', '100']) == '10'
    assert rg.latest_like('2024.05', ['2024.05', '2025.01']) == '2025.01'

def scan_run(log, pull_rc=0, scan_rc=1, stdout='{}', have=False):
    def run(cmd, **kw):
        log.append(cmd)
        class P: returncode = 0; stdout = '{}'; stderr = ''
        P.stdout = stdout
        if cmd[1:3] == ['image', 'inspect'] and '--format' not in cmd:
            P.returncode = 0 if have else 1
        elif cmd[1] == 'pull':
            P.returncode, P.stderr = pull_rc, 'denied: requested access to the resource is denied' if pull_rc else ''
        elif cmd[1:3] == ['scan', 'image']:
            P.returncode = scan_rc
        return P()
    return run

def test_the_image_is_pulled_before_it_is_scanned():
    log = []
    sc.scan('a:1', run=scan_run(log, have=True), binary='/bin/osv', docker='/bin/docker')
    kinds = [c[1] if c[0] == '/bin/docker' else 'osv' for c in log]
    assert kinds.index('pull') < kinds.index('osv')   # a stale copy already on the machine is refreshed, not trusted
    assert ['/bin/docker', 'image', 'rm', '-f', 'a:1'] not in log   # it was there before, so it stays

def test_a_failed_pull_is_an_error_and_still_cleans_up():
    log = []
    try:
        sc.scan('a:1', run=scan_run(log, pull_rc=1), binary='/bin/osv', docker='/bin/docker')
        assert False
    except RuntimeError as e:
        assert 'docker pull failed' in str(e) and 'denied' in str(e)
    assert ['/bin/docker', 'image', 'rm', '-f', 'a:1'] in log and not any(c[0] == '/bin/osv' for c in log)

def test_exit_128_is_a_clean_image_but_empty_output_with_findings_is_not():
    assert sc.scan('a:1', run=scan_run([], scan_rc=128), binary='/bin/osv', docker=None)['count'] == 0
    try:
        sc.scan('a:1', run=scan_run([], scan_rc=1, stdout=''), binary='/bin/osv', docker=None)
        assert False
    except RuntimeError as e:
        assert 'no result' in str(e)

def test_docker_calls_have_timeouts():
    seen = []
    def run(cmd, **kw):
        seen.append((cmd[1], kw.get('timeout')))
        class P: returncode = 0; stdout = '{}'; stderr = ''
        return P()
    sc.scan('a:1', run=run, binary='/bin/osv', docker='/bin/docker')
    assert all(t for _, t in seen)

def test_a_failing_license_lookup_does_not_blame_the_scan():
    scan = lambda ref: {**sc.summarize([]), 'labels': {'org.opencontainers.image.source': 'https://github.com/o/r'}}
    def boom(repo):
        raise RuntimeError('deps.dev down')
    got = im.lookup('a/b', '1', lambda n: ['1'], scan, lambda m: None, resolve=lambda *a: None, license_of=boom)
    assert got['vulns']['count'] == 0 and set(got['errors']) == {'license'}

def test_a_source_repo_cannot_be_a_dot_path():
    repo = lambda r: 'MIT'
    assert sc.image_license({'org.opencontainers.image.source': 'https://github.com/apache/.'}, repo) == (None, None)
    assert sc.image_license({'org.opencontainers.image.source': 'https://github.com/apache/..'}, repo) == (None, None)
    assert sc.image_license({'org.opencontainers.image.source': 'https://github.com/apache/airflow'}, repo) == ('MIT', 'source')

LOKI = {'results': [
    {'source': {'path': '/usr/bin/loki', 'type': 'artifact'}, 'packages': [
        {'package': {'name': 'github.com/redis/go-redis/v9', 'version': '9.18.0', 'ecosystem': 'Go'}, 'licenses': ['BSD-2-Clause']},
        {'package': {'name': 'github.com/grafana/loki/v3', 'version': '3.7.9', 'ecosystem': 'Go'}, 'licenses': ['AGPL-3.0', 'Apache-2.0', 'AGPL-3.0']}]},
    {'source': {'path': '/lib/apk/db/installed', 'type': 'os'}, 'packages': [
        {'package': {'name': 'musl', 'version': '1.2', 'ecosystem': 'Alpine'}, 'licenses': ['MIT']}]}]}

def test_the_main_package_is_the_one_named_like_the_image():
    assert sc.main_package(LOKI, 'docker.io/grafana/loki:3.7.9') == ('AGPL-3.0, Apache-2.0', 'github.com/grafana/loki/v3 3.7.9')
    minio = {'results': [{'packages': [{'package': {'name': 'minio', 'version': '0.2026', 'ecosystem': 'Wolfi'}, 'licenses': ['AGPL-3.0']}]}]}
    assert sc.main_package(minio, 'cgr.dev/chainguard/minio:latest') == ('AGPL-3.0', 'minio 0.2026')

def test_no_main_package_when_nothing_matches_or_the_license_is_unknown():
    debian = {'results': [{'packages': [{'package': {'name': 'postgresql-17', 'version': '17.11', 'ecosystem': 'Debian:13'}, 'licenses': ['UNKNOWN']},
                                        {'package': {'name': 'postgres', 'version': '17', 'ecosystem': 'Debian:13'}, 'licenses': ['UNKNOWN']}]}]}
    assert sc.main_package(debian, 'docker.io/library/postgres:17') is None
    assert sc.main_package(LOKI, 'docker.io/library/redis:7') is None

@pytest.fixture
def image_config():
    from repoconfig import config
    def apply(**block):
        settings.configure(config.dependency_settings(block))
    yield apply
    settings.reset()   # back to config/dependencies.json

def test_license_order_config_first_then_labels_then_the_main_package(image_config):
    repo = lambda r: {'jaegertracing/jaeger': 'Apache-2.0', 'o/labelled': 'MIT'}.get(r)
    image_config(image_licenses={'postgres': 'PostgreSQL'}, image_sources={'jaegertracing/all-in-one': 'jaegertracing/jaeger'})
    assert im.license_for('docker.io/library/postgres', None, None, repo) == ('PostgreSQL', 'config', None)   # any spelling, even unscanned
    assert im.license_for('docker.io/jaegertracing/all-in-one', {}, None, repo) == ('Apache-2.0', 'repo', 'github.com/jaegertracing/jaeger')
    labels = {'org.opencontainers.image.licenses': 'MIT'}
    assert im.license_for('docker.io/x/y', labels, ('AGPL-3.0', 'y 1'), repo) == ('MIT', 'label', None)
    assert im.license_for('docker.io/x/y', {}, ('AGPL-3.0', 'y 1'), repo) == ('AGPL-3.0', 'package', 'y 1')
    assert im.license_for('docker.io/x/y', {}, None, repo) is None

def test_a_configured_license_survives_a_failed_scan(image_config):
    image_config(image_licenses={'postgres': 'PostgreSQL'})
    def boom(ref):
        raise RuntimeError('docker pull failed: denied')
    got = im.lookup('docker.io/library/postgres', '17', lambda n: ['17'], boom, lambda m: None, resolve=lambda *a: None, license_of=lambda r: None)
    assert got['license'] == 'PostgreSQL' and got['license_of'] == 'config' and got['vulns'] is None and set(got['errors']) == {'vulns'}

def test_the_image_repository_comes_from_config_then_its_label_then_its_go_module(image_config):
    image_config(image_sources={'docker.langfuse.com/langfuse/langfuse': 'langfuse/langfuse'})
    assert im.image_repo('docker.langfuse.com/langfuse/langfuse', None, None) == 'langfuse/langfuse'
    assert im.image_repo('docker.io/x/y', {'org.opencontainers.image.source': 'https://github.com/o/r'}, None) == 'o/r'
    assert im.image_repo('docker.io/grafana/loki', {}, ('AGPL-3.0', 'github.com/grafana/loki/v3 3.7.9')) == 'grafana/loki'
    assert im.image_repo('docker.io/library/redis', {}, None) is None

def test_a_partial_or_variant_tag_resolves_among_tags_of_its_own_kind():
    digests = {'7': 'a', '7.4.12': 'a', 'alpine': 'b', '8.10.3-alpine': 'b', '8.10.3': 'c'}
    asked = []
    def digest(host, path, ref, auth=None):
        asked.append(ref)
        return digests.get(ref), None
    tags = ['7', '7.2.5', '7.4.12', '8.10.3', '8.10.3-alpine', 'alpine']
    assert rg.version_of('redis', '7', tags, digest=digest) == '7.4.12'
    assert '8.10.3' not in asked                                       # 7 only looks among 7.x tags
    assert rg.version_of('redis', 'alpine', tags, digest=digest) == '8.10.3-alpine'
    assert rg.version_of('redis', '7.4.12', tags, digest=digest) is None   # nothing more precise to find

def test_a_license_can_be_set_for_a_version_range(image_config):
    image_config(image_licenses={'redis@<7.4': 'BSD-3-Clause', 'redis@>=7.4,<8': 'RSAL OR SSPL', 'redis@>=8': 'RSAL OR SSPL OR AGPL'})
    none = lambda r: None
    assert im.license_for('docker.io/library/redis', {}, None, none, '7', '7.4.12') == ('RSAL OR SSPL', 'config', None)
    assert im.license_for('redis', {}, None, none, 'alpine', '8.10.3-alpine') == ('RSAL OR SSPL OR AGPL', 'config', None)
    assert im.license_for('redis', {}, None, none, '6') == ('BSD-3-Clause', 'config', None)   # every 6.x is before 7.4
    assert im.license_for('redis', {}, None, none, '7') is None                             # 7 unresolved: 7.2 or 7.4, unknown
    assert im.license_for('redis', {}, None, none, 'alpine') is None
