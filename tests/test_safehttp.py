import gzip, io, os, socket, sys, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
import requests
from common import safehttp as sh

def server(body, chunked=False, gz=False, pause=0.0):
    """A local HTTP server that sends `body` one byte at a time, `pause` seconds apart. Returns its URL."""
    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    srv.listen(1)
    if gz:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb') as f:
            f.write(body)
        body = buf.getvalue()
    def run():
        c, _ = srv.accept()
        try:
            c.recv(65536)
            head = b'HTTP/1.1 200 OK\r\n' + (b'Content-Encoding: gzip\r\n' if gz else b'')
            head += b'Transfer-Encoding: chunked\r\n\r\n' if chunked else b'Content-Length: %d\r\n\r\n' % len(body)
            c.sendall(head)
            step = 1 if pause else len(body)
            for i in range(0, len(body), step):
                part = body[i:i + step]
                c.sendall(b'%x\r\n%s\r\n' % (len(part), part) if chunked else part)
                time.sleep(pause)
            if chunked:
                c.sendall(b'0\r\n\r\n')
        except OSError:
            pass
        finally:
            c.close()
            srv.close()
    threading.Thread(target=run, daemon=True).start()
    return f'http://127.0.0.1:{srv.getsockname()[1]}/'

def fetch(url):
    return sh._read(requests.get(url, stream=True, timeout=10, headers={'Accept-Encoding': 'gzip'}))

@pytest.mark.parametrize('chunked,gz', [(False, False), (True, False), (False, True), (True, True)])
def test_a_body_is_read_whole(chunked, gz):
    assert fetch(server(b'{"tags": ["1", "2"]}', chunked=chunked, gz=gz)).json() == {'tags': ['1', '2']}

@pytest.mark.parametrize('chunked,gz', [(False, False), (True, False), (False, True)])
def test_a_dribbling_server_is_cut_off_at_the_deadline(monkeypatch, chunked, gz):
    monkeypatch.setattr(sh, 'DEADLINE', 1)
    url = server(b'x' * 60, chunked=chunked, gz=gz, pause=0.1)   # 6 s or more to send it all
    start = time.monotonic()
    with pytest.raises(RuntimeError, match='not complete'):
        fetch(url)
    assert time.monotonic() - start < 2.5

def test_a_gzip_bomb_stops_at_the_byte_cap(monkeypatch):
    monkeypatch.setattr(sh, 'MAX_BODY', 100_000)
    with pytest.raises(RuntimeError, match='over 100000 bytes'):
        fetch(server(b'\0' * 5_000_000, gz=True))   # 5 MB of zeros is about 5 KB gzipped

def test_other_compressions_are_refused():
    r = requests.Response()
    r.status_code, r.headers['Content-Encoding'], r.raw = 200, 'br', io.BytesIO(b'xx')
    with pytest.raises(RuntimeError, match='unsupported content encoding br'):
        sh._read(r)

def resolver(table):
    def resolve(name, port):
        if name not in table:
            raise OSError('no such host')
        return [(None, None, None, '', (a, port)) for a in table[name]]
    return resolve

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

def test_public_host_rejects_internal_targets():
    r = resolver({'registry-1.docker.io': ['44.208.254.194'], 'evil.example': ['169.254.169.254'], 'mixed.example': ['8.8.8.8', '10.0.0.5'], 'v6.example': ['2606:4700::1111']})
    assert sh.public_host('registry-1.docker.io', r) and sh.public_host('v6.example:5000', r)
    for host in ('169.254.169.254', 'localhost:5000', '[::1]:5000', 'evil.example', 'mixed.example', 'metadata.google.internal', 'nosuch.example', 'intranet'):
        assert not sh.public_host(host, r), host

class Sock:
    def __init__(self, ip):
        self.ip, self.closed = ip, False
    def getpeername(self):
        return (self.ip, 443)
    def close(self):
        self.closed = True

def test_connections_to_non_public_peers_are_refused():
    assert sh.check_peer(Sock('44.208.254.194')).ip == '44.208.254.194'
    for ip in ('169.254.169.254', '10.0.0.5', '127.0.0.1', '::1', 'fe80::1%eth0'):
        s = Sock(ip)
        try:
            sh.check_peer(s)
            assert False, ip
        except sh.requests.ConnectionError:
            assert s.closed

def test_session_uses_the_peer_checking_pool():
    adapter = sh.R.get_adapter('https://registry-1.docker.io/v2/')
    assert isinstance(adapter, sh.PublicAdapter) and adapter.poolmanager.pool_classes_by_scheme['https'] is sh.PublicHTTPSPool

def test_redirects_are_followed_by_hand_and_checked(monkeypatch):
    hops = []
    def fake_get(method, url, headers=None, params=None, timeout=None, allow_redirects=True, stream=False):
        assert allow_redirects is False
        hops.append((url, headers))
        if url == 'https://reg.example/a':
            return Resp(302, headers={'Location': 'https://cdn.example/b'})
        if url == 'https://cdn.example/b':
            return Resp(307, headers={'Location': 'http://169.254.169.254/latest/meta-data'})
        return Resp(200, {})
    monkeypatch.setattr(sh.R, 'request', fake_get)
    try:
        sh.get('https://reg.example/a', headers={'Authorization': 'Bearer t'}, is_public=lambda h: True)
        assert False
    except RuntimeError as e:
        assert 'refused' in str(e)
    assert hops == [('https://reg.example/a', {'Authorization': 'Bearer t'}), ('https://cdn.example/b', None)]

def test_retry_after_is_not_obeyed():
    assert sh.RETRY.respect_retry_after_header is False

def test_userinfo_in_a_url_is_never_public():
    for url in ('https://user:pw@localhost/x', 'https://10.0.0.1@evil.example/x', 'https://evil.example:pw@127.0.0.1/x'):
        try:
            sh.get(url)
            assert False, url
        except RuntimeError as e:
            assert 'refused' in str(e)
