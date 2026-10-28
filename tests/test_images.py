import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import images as im

def test_split_names_registry_and_repository_path():
    assert im.split('postgres') == ('registry-1.docker.io', 'library/postgres')
    assert im.split('docker.io/postgres') == ('registry-1.docker.io', 'library/postgres')
    assert im.split('grafana/loki') == ('registry-1.docker.io', 'grafana/loki')
    assert im.split('docker.langfuse.com/langfuse/langfuse') == ('docker.langfuse.com', 'langfuse/langfuse')
    assert im.split('localhost:5000/app') == ('localhost:5000', 'app')

def test_latest_keeps_the_shape_of_the_current_tag():
    assert im.latest_like('17', ['16', '17', '18', '18-alpine', '17.2', 'latest', '9']) == '18'
    assert im.latest_like('1.37', ['1.36', '1.37', '1.38', '1.38-musl', '1.4', 'latest']) == '1.38'
    assert im.latest_like('25.7-alpine', ['25.7-alpine', '25.12-alpine', '25.12', '26.1']) == '25.12-alpine'
    assert im.latest_like('0.8.0-pg16', ['0.8.0-pg16', '0.8.1-pg16', '0.9.0-pg17']) == '0.8.1-pg16'
    assert im.latest_like('v2.0.0', ['v2.0.0', 'v2.1.0', '2.2.0']) == 'v2.1.0'

def test_floating_tags_have_no_latest():
    assert im.latest_like('latest', ['latest', '1.0']) is None
    assert im.latest_like('alpine', ['alpine', '3.20']) is None

class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
    def json(self):
        return self._body
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

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
    assert im.tags('reg.example', 'a/b', get=get, is_public=lambda h: True) == ['1', '2']
    assert calls[-1][0] == 'https://reg.example/v2/a/b/tags/list?n=1000&last=1' and calls[-1][1] == {'Authorization': 'Bearer anon'}

def test_tags_refuses_a_non_https_token_realm():
    def get(url, headers=None, params=None):
        return Resp(401, headers={'WWW-Authenticate': 'Bearer realm="http://evil/token",service="x"'})
    try:
        im.tags('reg.example', 'a/b', get=get, is_public=lambda h: True)
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
    items = im.items_of(SCAN)
    assert [(i['id'], i['cve'], i['severity'], i['fixed']) for i in items] == [('CGA-1', 'CVE-2026-1', 'CRITICAL', '2.44-r11'), ('CGA-3', None, 'LOW', None)]
    assert items[0]['summary'] == 'glibc 2.44-r10: heap overflow' and items[1]['summary'] == 'glibc 2.44-r10: no fix yet'

def test_scan_runs_osv_scanner_without_secrets(monkeypatch):
    monkeypatch.setenv('GH_TOKEN', 'secret')
    seen = {}
    def run(cmd, **kw):
        seen.update(cmd=cmd, env=kw['env'])
        class P: returncode = 1; stdout = json.dumps(SCAN); stderr = ''
        return P()
    got = im.scan('postgres:17', run=run, binary='/bin/osv', docker=None)
    assert seen['cmd'] == ['/bin/osv', 'scan', 'image', '--format', 'json', 'postgres:17'] and 'secret' not in seen['env'].values()
    assert got['count'] == 2 and got['severity'] == 'CRITICAL' and got['fixed_in'] is None and got['fixable'] == 1 and got['unfixed'] == 1

def test_scan_error_exit_raises():
    def run(cmd, **kw):
        class P: returncode = 127; stdout = ''; stderr = 'pull access denied'
        return P()
    try:
        im.scan('private/app:1', run=run, binary='/bin/osv', docker=None)
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
    assert sorted(scanned) == ['postgres:17', 'redis:latest'] and deps[3]['vulns'] == {'count': 0}

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
    im.scan('new:1', run=run, binary='/bin/osv', docker='/bin/docker')
    im.scan('have:1', run=run, binary='/bin/osv', docker='/bin/docker')
    assert ['/bin/docker', 'image', 'rm', '-f', 'new:1'] in cmds and ['/bin/docker', 'image', 'rm', '-f', 'have:1'] not in cmds

def test_long_lists_keep_the_worst_items_and_exact_counts(monkeypatch):
    monkeypatch.setattr(im, 'MAX_ITEMS', 2)
    items = [{'id': str(n), 'severity': s, 'fixed': f, 'summary': str(n)} for n, (s, f) in enumerate([('LOW', None), ('CRITICAL', None), ('HIGH', '2'), ('CRITICAL', '1')])]
    got = im.summarize(items)
    assert [i['id'] for i in got['items']] == ['3', '1'] and got['count'] == 4 and got['fixable'] == 2 and got['unfixed'] == 2 and got['severity'] == 'CRITICAL'

def resolver(table):
    def resolve(name, port):
        if name not in table:
            raise OSError('no such host')
        return [(None, None, None, '', (a, port)) for a in table[name]]
    return resolve

def test_public_host_rejects_internal_targets():
    r = resolver({'registry-1.docker.io': ['44.208.254.194'], 'evil.example': ['169.254.169.254'], 'mixed.example': ['8.8.8.8', '10.0.0.5'], 'v6.example': ['2606:4700::1111']})
    assert im.public_host('registry-1.docker.io', r) and im.public_host('v6.example:5000', r)
    for host in ('169.254.169.254', 'localhost:5000', '[::1]:5000', 'evil.example', 'mixed.example', 'metadata.google.internal', 'nosuch.example', 'intranet'):
        assert not im.public_host(host, r), host

def test_images_on_internal_registries_are_never_fetched():
    deps = [{'ecosystem': 'docker', 'name': n, 'version': '1', 'latest': None, 'vulns': None} for n in ('169.254.169.254/x', 'localhost:5000/app')]
    logs = []
    im.annotate(deps, tags_of=lambda n: 1 / 0, scan=lambda r: 1 / 0, cache={}, log=logs.append, is_public=im.public_host)
    assert all(d['vulns'] is None and d['latest'] is None for d in deps) and len(logs) == 2

def test_token_realm_on_an_internal_host_is_refused():
    def get(url, headers=None, params=None):
        return Resp(401, headers={'WWW-Authenticate': 'Bearer realm="https://169.254.169.254/token",service="x"'})
    try:
        im.tags('reg.example', 'a/b', get=get, is_public=lambda h: not h.startswith('169.'))
        assert False
    except RuntimeError as e:
        assert 'realm' in str(e)

class Sock:
    def __init__(self, ip):
        self.ip, self.closed = ip, False
    def getpeername(self):
        return (self.ip, 443)
    def close(self):
        self.closed = True

def test_connections_to_non_public_peers_are_refused():
    assert im.check_peer(Sock('44.208.254.194')).ip == '44.208.254.194'
    for ip in ('169.254.169.254', '10.0.0.5', '127.0.0.1', '::1', 'fe80::1%eth0'):
        s = Sock(ip)
        try:
            im.check_peer(s)
            assert False, ip
        except im.requests.ConnectionError:
            assert s.closed

def test_session_uses_the_peer_checking_pool():
    adapter = im.R.get_adapter('https://registry-1.docker.io/v2/')
    assert isinstance(adapter, im.PublicAdapter) and adapter.poolmanager.pool_classes_by_scheme['https'] is im.PublicHTTPSPool

def test_redirects_are_followed_by_hand_and_checked(monkeypatch):
    hops = []
    def fake_get(method, url, headers=None, params=None, timeout=None, allow_redirects=True):
        assert allow_redirects is False
        hops.append((url, headers))
        if url == 'https://reg.example/a':
            return Resp(302, headers={'Location': 'https://cdn.example/b'})
        if url == 'https://cdn.example/b':
            return Resp(307, headers={'Location': 'http://169.254.169.254/latest/meta-data'})
        return Resp(200, {})
    monkeypatch.setattr(im.R, 'request', fake_get)
    try:
        im._get('https://reg.example/a', headers={'Authorization': 'Bearer t'}, is_public=lambda h: True)
        assert False
    except RuntimeError as e:
        assert 'refused' in str(e)
    assert hops == [('https://reg.example/a', {'Authorization': 'Bearer t'}), ('https://cdn.example/b', None)]

def test_floating_tag_resolves_to_the_version_with_the_same_digest():
    digests = {'latest': 'sha256:b', '12.3.0': 'sha256:c', '12.2.1': 'sha256:b', '12.2': 'sha256:b'}
    asked = []
    def digest(host, path, ref, auth=None):
        asked.append(ref)
        return digests.get(ref), {'Authorization': 'Bearer t'}
    tags = ['latest', '12.2', '12.2.1', '12.3.0', '12.3.0-ubuntu', 'main', '9.5.0']
    assert im.version_of('grafana/grafana', 'latest', tags, digest=digest) == '12.2.1'
    assert asked == ['latest', '12.3.0', '12.2.1']

def test_floating_tag_without_a_match_stays_floating():
    def digest(host, path, ref, auth=None):
        return ('sha256:x' if ref == 'latest' else 'sha256:y'), None
    assert im.version_of('a/b', 'latest', ['1.0.0', '2.0.0'], digest=digest, limit=1) is None

def test_annotate_shows_the_version_behind_latest():
    deps = [{'ecosystem': 'docker', 'name': 'grafana/grafana', 'version': 'latest', 'latest': None, 'vulns': None}]
    im.annotate(deps, tags_of=lambda n: ['12.2.1', '12.3.0'], scan=lambda r: im.summarize([]), cache={}, is_public=lambda h: True,
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
    d, auth = im.digest('reg.example', 'a/b', 'latest', get=get, is_public=lambda h: True)
    assert d == 'sha256:abc' and auth == {'Authorization': 'Bearer anon'}
    assert calls[0][0] == 'HEAD' and 'image.index' in calls[0][2]['Accept'] and calls[-1][0] == 'HEAD'

def test_the_same_advisory_on_the_same_package_counts_once():
    pkg = SCAN['results'][0]['packages'][0]
    twice = {'results': [{'packages': [pkg, pkg]}]}
    assert len(im.items_of(twice)) == 2

def test_image_license_from_label_then_source_repo():
    repo = lambda r: {'grafana/grafana': 'AGPL-3.0'}.get(r)
    assert im.image_license({'org.opencontainers.image.licenses': 'MIT'}, repo) == ('MIT', 'label')
    assert im.image_license({'org.opencontainers.image.licenses': 'Apache License 2.0'}, repo) == ('Apache-2.0', 'label')
    assert im.image_license({'org.opencontainers.image.source': 'https://github.com/grafana/grafana'}, repo) == ('AGPL-3.0', 'source')
    assert im.image_license({'org.label-schema.vcs-url': 'https://github.com/grafana/grafana.git'}, repo) == ('AGPL-3.0', 'source')
    assert im.image_license({'org.opencontainers.image.source': 'https://gitlab.com/a/b'}, repo) == (None, None)
    assert im.image_license({'org.opencontainers.image.source': 'https://github.com/../x'}, repo) == (None, None)
    assert im.image_license({}, repo) == (None, None)

def test_scan_reads_labels_from_the_pulled_image():
    def run(cmd, **kw):
        class P: returncode = 0; stdout = '{}'; stderr = ''
        if cmd[1:3] == ['image', 'inspect'] and '--format' in cmd:
            P.stdout = '{"org.opencontainers.image.licenses": "MIT"}'
        return P()
    got = im.scan('a:1', run=run, binary='/bin/osv', docker='/bin/docker')
    assert got['labels'] == {'org.opencontainers.image.licenses': 'MIT'} and got['count'] == 0

def test_annotate_sets_the_image_license():
    deps = [{'ecosystem': 'docker', 'name': 'grafana/grafana', 'version': '13.2.2', 'latest': None, 'vulns': None}]
    scan = lambda ref: {**im.summarize([]), 'labels': {'org.opencontainers.image.source': 'https://github.com/grafana/grafana'}}
    im.annotate(deps, tags_of=lambda n: ['13.2.2'], scan=scan, cache={}, is_public=lambda h: True, license_of=lambda r: 'AGPL-3.0')
    assert deps[0]['license'] == 'AGPL-3.0' and deps[0]['license_of'] == 'source' and 'labels' not in deps[0]['vulns']
