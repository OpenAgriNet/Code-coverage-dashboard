"""Container registries over the registry HTTP API v2: tag lists, content digests, and the newest tag of the same shape."""
import re
from urllib.parse import urlsplit
from common.safehttp import get as _get, public_host
from stackinfo import settings

# image names and tags come from compose files, Dockerfiles and charts in the tracked repos
NAME=re.compile(r'[a-z0-9][a-z0-9._-]*(?::\d+)?(?:/[a-z0-9][a-z0-9._-]*)*')
TAG=re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}')
SHAPE=re.compile(r'(v?)(\d+(?:\.\d+)*)(.*)')
def split(name):
 """(registry host, repository path) the registry API is asked for: Docker Hub is registry-1.docker.io, its official images live under library/."""
 p=name.split('/');host=len(p)>1 and ('.' in p[0] or ':' in p[0] or p[0]=='localhost')
 reg,path=(p[0],p[1:]) if host else ('docker.io',p)
 if reg=='docker.io':return 'registry-1.docker.io','/'.join(['library',*path] if len(path)==1 else path)
 return reg,'/'.join(path)
def canonical(name):
 """One spelling per image: postgres, docker.io/postgres and docker.io/library/postgres are the same image, so they are looked up,
 scanned and removed once (scanning both spellings at once also let one scan delete the image the other was reading)."""
 host,path=split(name)
 return f'docker.io/{path}' if host=='registry-1.docker.io' else f'{host}/{path}'
def latest_like(tag,tags):
 """Highest tag with the same prefix, number of version parts and suffix as tag; None for a floating tag such as latest or alpine."""
 m=SHAPE.fullmatch(tag)
 if not m:return None
 pre,nums,suf=m.group(1),m.group(2).count('.'),m.group(3);digits=len(m.group(2).split('.')[0])
 # a build number or a date (20250101) is not the next major of 17: the first number may grow by one digit at most
 same=[t for t in tags for x in [SHAPE.fullmatch(t)] if x and x.group(1)==pre and x.group(2).count('.')==nums and x.group(3)==suf and len(x.group(2).split('.')[0])<=digits+1]
 return max(same,key=lambda t:tuple(int(n) for n in SHAPE.fullmatch(t).group(2).split('.')),default=None)
def _challenge(header):
 return dict(re.findall(r'(\w+)="([^"]*)"',header or ''))
def _authorize(host,r,get,is_public):
 """Anonymous bearer token for the registry's 401 challenge; the token realm must be a public https host."""
 c=_challenge(r.headers.get('WWW-Authenticate'))
 realm=urlsplit(c.get('realm',''))
 if realm.scheme!='https' or not realm.hostname or not is_public(realm.netloc):raise RuntimeError(f'registry {host} asked for a token from a non-https or non-public realm')
 t=get(c['realm'],params={k:c[k] for k in ('service','scope') if k in c});t.raise_for_status()
 tok=t.json();return {'Authorization':'Bearer '+(tok.get('token') or tok.get('access_token') or '')}
ACCEPT=', '.join(('application/vnd.oci.image.index.v1+json','application/vnd.docker.distribution.manifest.list.v2+json',
 'application/vnd.oci.image.manifest.v1+json','application/vnd.docker.distribution.manifest.v2+json'))
def digest(host,path,ref,get=_get,is_public=public_host,auth=None):
 """(content digest of host/path:ref, auth to reuse). A HEAD request, which Docker Hub does not count against its pull limit."""
 url=f'https://{host}/v2/{path}/manifests/{ref}';h={'Accept':ACCEPT}
 r=get(url,headers={**h,**(auth or {})},method='HEAD')
 if r.status_code==401 and auth is None:auth=_authorize(host,r,get,is_public);r=get(url,headers={**h,**auth},method='HEAD')
 return (r.headers.get('Docker-Content-Digest') if r.status_code==200 else None),auth
def version_of(name,tag,tags,digest=digest,limit=None):
 """The version tag that points at the same image as tag, or None: a floating tag (latest, or alpine among 8.10.3-alpine tags)
 or a partial version (7, which is 7.4.12 today; 15-alpine). Only tags of the same variant are tried (latest: plain versions;
 alpine and 15-alpine: -alpine ones; 7: 7.x ones), newest first (12.2.1 before 12.2 before 12), at most
 dependencies.images.resolve_limit of them."""
 m=SHAPE.fullmatch(tag)
 base,suf=(m.group(2)+'.',m.group(3)) if m else ('','' if tag=='latest' else '-'+tag)
 plain=[t for t in tags for x in [SHAPE.fullmatch(t)] if x and x.group(3)==suf and x.group(2).startswith(base) and t!=tag]
 if not plain:return None
 host,path=split(name);want,auth=digest(host,path,tag)
 if not want:return None
 plain.sort(key=lambda t:tuple(int(n) for n in SHAPE.fullmatch(t).group(2).split('.')),reverse=True)
 for t in plain[:settings.get('images','resolve_limit') if limit is None else limit]:
  got,auth=digest(host,path,t,auth=auth)
  if got==want:return t
 return None
def tags(host,path,get=_get,pages=None,is_public=public_host):
 """Every tag of host/path from the registry HTTP API v2, with an anonymous bearer token when the registry asks for one."""
 base=f'https://{host}';url=f'{base}/v2/{path}/tags/list?n=1000';auth=None;out=[];pages=pages or settings.get('images','max_tag_pages')
 for _ in range(pages):
  r=get(url,headers=auth)
  if r.status_code==401 and auth is None:
   auth=_authorize(host,r,get,is_public);r=get(url,headers=auth)
  r.raise_for_status();out+=r.json().get('tags') or []
  nxt=re.search(r'<([^>]+)>;\s*rel="next"',r.headers.get('Link') or '')
  if not nxt:return out
  url=base+nxt.group(1) if nxt.group(1).startswith('/') else nxt.group(1)
  if not url.startswith(base+'/'):raise RuntimeError(f'{host} sent its next page of tags from another host')
 raise RuntimeError(f'{host}/{path} has more than {pages} pages of tags; the newest could be on a page not read')
def gone_from_docker_hub(name,get=_get):
 """True when Docker Hub says the image's repository does not exist (404). Its registry answers 401 both for a private image and
 for one that is gone, so the Hub's own API tells the two apart (minio/minio and minio/mc were removed in 2025)."""
 host,path=split(name)
 if host!='registry-1.docker.io':return False
 try:return get(f'https://hub.docker.com/v2/repositories/{path}/').status_code==404
 except Exception:return False
GONE='no longer on Docker Hub: the repository does not exist there any more (404), so it cannot be pulled'
def tags_of(name):
 return tags(*split(name))
