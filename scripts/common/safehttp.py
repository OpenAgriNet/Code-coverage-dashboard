"""HTTPS to servers we do not control (registries, token services): public hosts only, the connected address checked, redirects
followed by hand, responses capped in size and time. Image names and registry answers come from tracked repos and remote servers."""
import ipaddress, re, socket, time
from urllib.parse import urlsplit
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool

def public_host(host,resolve=socket.getaddrinfo):
 """True when host (optionally host:port) is a DNS name whose every address is public. Image names come from tracked repos, so a
 name such as 169.254.169.254/x or localhost:5000/x must not make the runner call its metadata service or local ports."""
 name=host.rsplit(':',1)[0] if re.fullmatch(r'[^:]+:\d+',host) else host
 try:ipaddress.ip_address(name.strip('[]'));return False   # IP literals are never registries we track
 except ValueError:pass
 if name=='localhost' or name.endswith(('.localhost','.local','.internal')) or '.' not in name:return False
 try:addrs={a[4][0] for a in resolve(name,443)}
 except OSError:return False
 return bool(addrs) and all(ipaddress.ip_address(a.split('%')[0]).is_global for a in addrs)
def check_peer(sock):
 """Refuse a connection whose peer is not a public address. Checked on the connected socket, so a DNS answer that changes
 between public_host() and the request (rebinding) cannot reach the metadata service or a private network."""
 ip=sock.getpeername()[0]
 if not ipaddress.ip_address(ip.split('%')[0]).is_global:
  sock.close();raise requests.ConnectionError(f'refused to talk to non-public address {ip}')
 return sock
class PublicHTTPSConnection(HTTPSConnection):
 def _new_conn(self):return check_peer(super()._new_conn())
class PublicHTTPSPool(HTTPSConnectionPool):
 ConnectionCls=PublicHTTPSConnection
class PublicAdapter(HTTPAdapter):
 def init_poolmanager(self,*a,**kw):
  super().init_poolmanager(*a,**kw);self.poolmanager.pool_classes_by_scheme={**self.poolmanager.pool_classes_by_scheme,'https':PublicHTTPSPool}
R=requests.Session()   # no GitHub headers or tokens: registries are third parties
R.trust_env=False      # no proxy or netrc credentials from the environment
# timeouts and 5xx are retried; redirects are returned so _get can check each hop
# respect_retry_after_header is off: a hostile registry could otherwise answer 429 with Retry-After: 86400 and park a worker for a day
RETRY=Retry(total=3,connect=3,read=3,status=3,redirect=0,raise_on_redirect=False,backoff_factor=1,respect_retry_after_header=False,status_forcelist=(429,500,502,503,504),allowed_methods=None)
R.mount('https://',PublicAdapter(max_retries=RETRY));R.mount('http://',HTTPAdapter(max_retries=0))
MAX_REDIRECTS=5
MAX_BODY=5_000_000   # a tag page or a manifest is far smaller
DEADLINE=60          # seconds to receive one response, however slowly the server sends it
def _read(r):
 """Read the body in chunks under a byte cap and an overall deadline: requests' timeout is per socket read, so a server that
 dribbles bytes would otherwise hold a worker for as long as it likes."""
 end=time.monotonic()+DEADLINE;body=bytearray()
 for chunk in r.iter_content(65536):
  body+=chunk
  if len(body)>MAX_BODY:r.close();raise RuntimeError(f'response over {MAX_BODY} bytes')
  if time.monotonic()>end:r.close();raise RuntimeError(f'response not complete after {DEADLINE} s')
 r._content=bytes(body);r._content_consumed=True
 return r
def get(url,headers=None,params=None,is_public=None,method='GET'):
 """GET (or HEAD) over https only, following redirects by hand so every hop is checked like the first one."""
 is_public=is_public or public_host
 for _ in range(MAX_REDIRECTS+1):
  u=urlsplit(url)
  if u.scheme!='https' or not u.hostname or not is_public(u.netloc):raise RuntimeError(f'refused to fetch {u.scheme}://{u.netloc}: not a public https host')
  r=R.request(method,url,headers=headers,params=params,timeout=30,allow_redirects=False,stream=True)
  if r.status_code not in (301,302,303,307,308):return _read(r)
  r.close()
  url=requests.compat.urljoin(url,r.headers.get('Location',''));params=None
  if urlsplit(url).netloc!=u.netloc:headers=None   # never carry a registry token to another host
 raise RuntimeError('too many redirects')
