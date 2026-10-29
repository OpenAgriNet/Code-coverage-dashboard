import io, zipfile
from stackinfo.lookups import wheel as w

def wheel_bytes(metadata):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('pkg/__init__.py', 'x' * 50000)
        z.writestr('pkg-1.0.dist-info/METADATA', metadata)
    return b.getvalue()

def server(data):
    asked = []
    class R:
        def __init__(self, body, total): self.status_code, self.content, self.headers = 206, body, {'Content-Range': f'bytes 0-0/{total}'}
    def get(url, plain):
        a, b = map(int, plain['Range'][len('bytes='):].split('-'))
        asked.append((a, b))
        return R(data[a:b + 1], len(data))
    return get, asked

URL = 'https://github.com/o/r/releases/download/v1/pkg-1.0-py3-none-any.whl'

def test_the_wheel_metadata_license_is_read_without_fetching_the_whole_wheel():
    data = wheel_bytes('Metadata-Version: 2.1\nName: pkg\nLicense: MIT\n')
    get, asked = server(data)
    assert w.wheel_license(URL, get=get) == 'MIT'
    assert sum(b - a + 1 for a, b in asked) < len(data)

def test_a_license_expression_wins_and_prose_is_not_a_license():
    get, _ = server(wheel_bytes('Name: pkg\nLicense-Expression: Apache-2.0\nLicense: whatever\n'))
    assert w.wheel_license(URL, get=get) == 'Apache-2.0'
    get, _ = server(wheel_bytes('Name: pkg\nLicense: see the LICENSE file\n'))
    assert w.wheel_license(URL, get=get) is None

def test_only_https_wheels_are_read():
    assert w.wheel_license('http://x/pkg.whl', get=None) is None
    assert w.wheel_license('https://x/pkg.tar.gz', get=None) is None
