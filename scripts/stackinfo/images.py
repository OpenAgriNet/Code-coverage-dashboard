"""Docker images: the newest tag of the same shape (17 -> 18, 25.7-alpine -> 25.12-alpine) from the registry's tag list, and the
known vulnerabilities of the packages inside the image from osv-scanner (it pulls and reads the image; nothing in it is run).
Registries are asked anonymously, so private images stay unchecked."""
import ipaddress, json, os, re, shutil, socket, subprocess, sys
from urllib.parse import quote, urlsplit
from concurrent.futures import ThreadPoolExecutor
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from .analyser import child_env
from .depsdev import D
from .reasons import short_error
from .vulns import SEVERITIES, normal, severity as osv_severity
WORKERS=4
MAX_ITEMS=50   # postgres alone has hundreds; the counts stay exact, the list keeps the worst
SCAN_TIMEOUT=900
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
def latest_like(tag,tags):
 """Highest tag with the same prefix, number of version parts and suffix as tag; None for a floating tag such as latest or alpine."""
 m=SHAPE.fullmatch(tag)
 if not m:return None
 pre,nums,suf=m.group(1),m.group(2).count('.'),m.group(3)
 same=[t for t in tags for x in [SHAPE.fullmatch(t)] if x and x.group(1)==pre and x.group(2).count('.')==nums and x.group(3)==suf]
 return max(same,key=lambda t:tuple(int(n) for n in SHAPE.fullmatch(t).group(2).split('.')),default=None)
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
RETRY=Retry(total=3,connect=3,read=3,status=3,redirect=0,raise_on_redirect=False,backoff_factor=1,status_forcelist=(429,500,502,503,504),allowed_methods=None)
R.mount('https://',PublicAdapter(max_retries=RETRY));R.mount('http://',HTTPAdapter(max_retries=0))
MAX_REDIRECTS=5
def _get(url,headers=None,params=None,is_public=None,method='GET'):
 """GET (or HEAD) over https only, following redirects by hand so every hop is checked like the first one."""
 is_public=is_public or public_host
 for _ in range(MAX_REDIRECTS+1):
  u=urlsplit(url)
  if u.scheme!='https' or not u.hostname or not is_public(u.netloc):raise RuntimeError(f'refused to fetch {u.scheme}://{u.netloc}: not a public https host')
  r=R.request(method,url,headers=headers,params=params,timeout=30,allow_redirects=False)
  if r.status_code not in (301,302,303,307,308):return r
  url=requests.compat.urljoin(url,r.headers.get('Location',''));params=None
  if urlsplit(url).netloc!=u.netloc:headers=None   # never carry a registry token to another host
 raise RuntimeError('too many redirects')
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
RESOLVE_LIMIT=30
def version_of(name,tag,tags,digest=digest,limit=None):
 """The version tag that points at the same image as a floating tag such as latest, or None. Plain version tags are tried
 newest first (12.2.1 before 12.2 before 12), at most RESOLVE_LIMIT of them."""
 host,path=split(name);want,auth=digest(host,path,tag)
 if not want:return None
 plain=[t for t in tags for m in [SHAPE.fullmatch(t)] if m and not m.group(3)]
 plain.sort(key=lambda t:tuple(int(n) for n in SHAPE.fullmatch(t).group(2).split('.')),reverse=True)
 for t in plain[:limit or RESOLVE_LIMIT]:
  got,auth=digest(host,path,t,auth=auth)
  if got==want:return t
 return None
def tags(host,path,get=_get,pages=50,is_public=public_host):
 """Every tag of host/path from the registry HTTP API v2, with an anonymous bearer token when the registry asks for one."""
 base=f'https://{host}';url=f'{base}/v2/{path}/tags/list?n=1000';auth=None;out=[]
 for _ in range(pages):
  r=get(url,headers=auth)
  if r.status_code==401 and auth is None:
   auth=_authorize(host,r,get,is_public);r=get(url,headers=auth)
  r.raise_for_status();out+=r.json().get('tags') or []
  nxt=re.search(r'<([^>]+)>;\s*rel="next"',r.headers.get('Link') or '')
  if not nxt:return out
  url=base+nxt.group(1) if nxt.group(1).startswith('/') else nxt.group(1)
  if not url.startswith(base+'/'):return out
 return out
def tags_of(name):
 return tags(*split(name))
def loose(v):
 """Sort key from every number in a version, so OS package revisions compare (2.44-r10 < 2.44-r11, 1:2.3-4 < 1:2.3-5)."""
 return tuple(int(n) for n in re.findall(r'\d+',str(v)))
def fixed_after(rec,eco,name,ver):
 """Lowest fixed version above ver in this advisory's entries for the package (commit ranges ignored)."""
 cur=loose(ver);fixes=[e['fixed'] for a in rec.get('affected') or [] for p in [a.get('package') or {}]
  if p.get('ecosystem','').split(':')[0]==eco.split(':')[0] and normal(p.get('name',''))==normal(name)
  for rg in a.get('ranges') or [] if rg.get('type')!='GIT' for e in rg.get('events') or [] if e.get('fixed') and loose(e['fixed'])>cur]
 return min(fixes,key=loose,default=None)
def _score(s):
 try:x=float(s)
 except (TypeError,ValueError):return None
 return 'CRITICAL' if x>=9 else 'HIGH' if x>=7 else 'MODERATE' if x>=4 else 'LOW' if x>0 else None
def items_of(result):
 """One vulnerability item per package and advisory group in osv-scanner's JSON, in the shape vulns.py gives OSV advisories."""
 out=[];seen=set()
 for res in result.get('results') or []:
  for p in res.get('packages') or []:
   pkg=p.get('package') or {};name,ver,eco=pkg.get('name',''),pkg.get('version',''),pkg.get('ecosystem','')
   recs={v['id']:v for v in p.get('vulnerabilities') or [] if v.get('id')}
   for g in p.get('groups') or []:
    ids=g.get('ids') or [];rec=next((recs[i] for i in ids if i in recs),{})
    sev=_score(g.get('max_severity')) or osv_severity(rec)
    fixes=[f for i in ids if i in recs for f in [fixed_after(recs[i],eco,name,ver)] if f]
    text=rec.get('summary') or (rec.get('details') or '').split('\n')[0][:160] or 'known vulnerability'
    vid=ids[0] if ids else '?'
    if (vid,name,ver) in seen:continue   # the same package can be listed once per layer or sub-package
    seen.add((vid,name,ver))
    out.append({'id':vid,'cve':next((a for a in g.get('aliases') or [] if a.startswith('CVE-')),None),'summary':f'{name} {ver}: {text}',
     'severity':sev,'fixed':min(fixes,key=loose) if fixes else None,'url':f'https://osv.dev/vulnerability/{vid}'})
 return out
def summarize(items):
 """Like vulns.summarize, but no single fixed_in: the fixes belong to different packages inside the image.
 items keeps the MAX_ITEMS worst (fixable first within a severity); count, fixable and unfixed cover all of them."""
 rank=lambda i:SEVERITIES.index(i['severity']) if i['severity'] in SEVERITIES else -1
 fixable=sum(1 for i in items if i['fixed'])
 worst=sorted(items,key=lambda i:(-rank(i),i['fixed'] is None,i['summary']))
 return {'count':len(items),'severity':worst[0]['severity'] if items else None,'fixed_in':None,'fixable':fixable,'unfixed':len(items)-fixable,'items':worst[:MAX_ITEMS]}
def scan(ref,run=subprocess.run,binary=None,docker=shutil.which('docker')):
 """osv-scanner pulls the image through the docker CLI; an image that was not on the machine before is removed again, so a run
 over dozens of images does not fill the disk."""
 binary=binary or os.getenv('OSV_SCANNER') or shutil.which('osv-scanner')
 if not binary:raise RuntimeError('osv-scanner is not installed')
 env=child_env()
 had=docker and run([docker,'image','inspect',ref],capture_output=True,env=env).returncode==0
 labels={}
 try:
  p=run([binary,'scan','image','--format','json',ref],capture_output=True,text=True,timeout=SCAN_TIMEOUT,env=env)
  if docker:labels=_labels(run([docker,'image','inspect','--format','{{json .Config.Labels}}',ref],capture_output=True,text=True,env=env))
 finally:
  if docker and not had:run([docker,'image','rm','-f',ref],capture_output=True,env=env)
 if p.returncode==128:return {**summarize([]),'labels':labels}   # no packages found in the image
 if p.returncode not in (0,1):
  last=(p.stderr or '').strip().splitlines()
  raise RuntimeError(f'osv-scanner exit {p.returncode}: {last[-1][:150] if last else "no output"}')
 return {**summarize(items_of(json.loads(p.stdout))),'labels':labels}
def _labels(p):
 """The image's config labels from docker image inspect (read from the pulled image: no extra registry request)."""
 try:got=json.loads(p.stdout) if p.returncode==0 else None
 except (TypeError,ValueError):return {}
 return {str(k):str(v) for k,v in got.items()} if isinstance(got,dict) else {}
# license texts images put in labels -> SPDX ids the policy knows
SPDX={'apache license 2.0':'Apache-2.0','apache license, version 2.0':'Apache-2.0','apache 2.0':'Apache-2.0','apache-2':'Apache-2.0','apache2':'Apache-2.0',
 'mit license':'MIT','the mit license':'MIT','bsd':'BSD-3-Clause','gplv3':'GPL-3.0-only','gplv2':'GPL-2.0-only','agplv3':'AGPL-3.0-only','mpl 2.0':'MPL-2.0'}
LABEL_LICENSE=('org.opencontainers.image.licenses','org.label-schema.license','license')
LABEL_SOURCE=('org.opencontainers.image.source','org.label-schema.vcs-url')
GITHUB_REPO=re.compile(r'(?:https?://|git@)?github\.com[/:]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?(?:[#?].*)?')
def image_license(labels,repo_license):
 """(license, where): the image's own license label, else the license of the GitHub repo its source label names, else (None, None).
 repo_license('owner/repo') gives that repo's SPDX id."""
 lic=next((labels[k].strip() for k in LABEL_LICENSE if labels.get(k,'').strip()),None)
 if lic:return SPDX.get(lic.lower(),lic),'label'
 src=next((labels[k].strip() for k in LABEL_SOURCE if labels.get(k,'').strip()),'')
 m=GITHUB_REPO.fullmatch(src)
 if m and '..' not in m.group(1):
  lic=repo_license(m.group(1))
  if lic:return lic,'source'
 return None,None
LICENSES={}
def project_license(repo,github=None):
 """SPDX license of a GitHub repo: deps.dev's answer (no GitHub API quota), or GitHub's own license detection when deps.dev
 cannot name it ('non-standard', as for the MPL-2.0 HashiCorp providers). Cached per run."""
 if repo in LICENSES:return LICENSES[repo]
 r=D.get(f'https://api.deps.dev/v3/projects/{quote("github.com/"+repo,safe="")}',timeout=30)
 lic=None
 if r.status_code!=404:r.raise_for_status();lic=r.json().get('license')
 if not lic or lic in ('non-standard','NOASSERTION'):
  import aggregate_coverage as ac
  got=((github or ac.api)(f'/repos/{repo}/license') or {}).get('license') or {}
  lic=got.get('spdx_id') if got.get('spdx_id') not in (None,'NOASSERTION') else None
 LICENSES[repo]=lic
 return lic
CACHE={}
def lookup(name,tag,tags_of,scan,log,resolve=version_of,license_of=None):
 license_of=license_of or project_license
 out={'latest':None,'latest_of':None,'vulns':None};errors={}
 try:
  if SHAPE.fullmatch(tag):out['latest']=latest_like(tag,tags_of(name));out['latest_of']='registry'
  else:
   # a floating tag (latest): find the version it points at today, then compare that version with the newest
   out['latest_of']='floating';ts=tags_of(name);v=resolve(name,tag,ts)
   if v:out.update(resolved=v,latest=latest_like(v,ts),latest_of='registry')
 except Exception as e:errors['latest']=short_error(e);log(f'WARN registry tags failed for {name}: {e}')
 try:
  res=scan(f'{name}:{tag}');labels=res.pop('labels',{})
  out['vulns']={'checked_version':tag,'exact':True,**res}
  lic,where=image_license(labels,license_of)
  if lic:out.update(license=lic,license_of=where)
 except Exception as e:errors['vulns']=errors['license']=short_error(e);log(f'WARN image scan failed for {name}:{tag}: {e}')
 if errors:out['errors']=errors
 return out
def annotate(deps,tags_of=tags_of,scan=scan,cache=CACHE,log=lambda m:print(m,file=sys.stderr),workers=WORKERS,is_public=public_host,resolve=version_of,license_of=None):
 """Fill latest, latest_of and vulns of every Docker image in deps. An unresolved ${VAR} tag, a malformed name, a refused pull or a
 failed scan leaves vulns None (not checked), never 'none known'. Each image:tag is looked up once per run, several at a time."""
 rows=[]
 for d in deps:
  if d.get('ecosystem')!='docker':continue
  name,tag=d['name'],str(d.get('version') or 'latest')
  if not NAME.fullmatch(name) or '..' in name or not TAG.fullmatch(tag):
   if '$' not in tag:log(f'WARN image reference not checked: {name}:{tag}')
   continue
  if not is_public(split(name)[0]):log(f'WARN image not checked, registry is not a public host: {name}');continue
  rows.append((d,(name,tag)))
 todo=sorted({k for _,k in rows if k not in cache})
 with ThreadPoolExecutor(max_workers=workers) as ex:
  for k,res in zip(todo,ex.map(lambda k:lookup(*k,tags_of,scan,log,resolve,license_of),todo)):cache[k]=res
 for d,k in rows:d.update({x:(dict(v) if isinstance(v,dict) else v) for x,v in cache[k].items()})
