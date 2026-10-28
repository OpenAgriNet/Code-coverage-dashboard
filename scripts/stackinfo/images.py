"""Docker images: the newest tag of the same shape (17 -> 18, 25.7-alpine -> 25.12-alpine) from the registry's tag list, and the
known vulnerabilities of the packages inside the image from osv-scanner (it pulls and reads the image; nothing in it is run).
Registries are asked anonymously, so private images stay unchecked."""
import json, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import requests
from .analyser import child_env
from .vulns import SEVERITIES, normal, severity as osv_severity
R=requests.Session()   # no GitHub headers or tokens: registries are third parties
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
def latest_like(tag,tags):
 """Highest tag with the same prefix, number of version parts and suffix as tag; None for a floating tag such as latest or alpine."""
 m=SHAPE.fullmatch(tag)
 if not m:return None
 pre,nums,suf=m.group(1),m.group(2).count('.'),m.group(3)
 same=[t for t in tags for x in [SHAPE.fullmatch(t)] if x and x.group(1)==pre and x.group(2).count('.')==nums and x.group(3)==suf]
 return max(same,key=lambda t:tuple(int(n) for n in SHAPE.fullmatch(t).group(2).split('.')),default=None)
def _get(url,headers=None,params=None):
 return R.get(url,headers=headers,params=params,timeout=30)
def _challenge(header):
 return dict(re.findall(r'(\w+)="([^"]*)"',header or ''))
def tags(host,path,get=_get,pages=50):
 """Every tag of host/path from the registry HTTP API v2, with an anonymous bearer token when the registry asks for one."""
 base=f'https://{host}';url=f'{base}/v2/{path}/tags/list?n=1000';auth=None;out=[]
 for _ in range(pages):
  r=get(url,headers=auth)
  if r.status_code==401 and auth is None:
   c=_challenge(r.headers.get('WWW-Authenticate'))
   if not c.get('realm','').startswith('https://'):raise RuntimeError(f'registry {host} asked for a token from a non-https realm')
   t=get(c['realm'],params={k:c[k] for k in ('service','scope') if k in c});t.raise_for_status()
   tok=t.json();auth={'Authorization':'Bearer '+(tok.get('token') or tok.get('access_token') or '')}
   r=get(url,headers=auth)
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
 out=[]
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
 try:p=run([binary,'scan','image','--format','json',ref],capture_output=True,text=True,timeout=SCAN_TIMEOUT,env=env)
 finally:
  if docker and not had:run([docker,'image','rm','-f',ref],capture_output=True,env=env)
 if p.returncode==128:return summarize([])   # no packages found in the image
 if p.returncode not in (0,1):
  last=(p.stderr or '').strip().splitlines()
  raise RuntimeError(f'osv-scanner exit {p.returncode}: {last[-1][:150] if last else "no output"}')
 return summarize(items_of(json.loads(p.stdout)))
CACHE={}
def lookup(name,tag,tags_of,scan,log):
 out={'latest':None,'latest_of':None,'vulns':None}
 if not SHAPE.fullmatch(tag):out['latest_of']='floating'
 else:
  try:out['latest']=latest_like(tag,tags_of(name));out['latest_of']='registry'
  except Exception as e:log(f'WARN registry tags failed for {name}: {e}')
 try:out['vulns']={'checked_version':tag,'exact':True,**scan(f'{name}:{tag}')}
 except Exception as e:log(f'WARN image scan failed for {name}:{tag}: {e}')
 return out
def annotate(deps,tags_of=tags_of,scan=scan,cache=CACHE,log=lambda m:print(m,file=sys.stderr),workers=WORKERS):
 """Fill latest, latest_of and vulns of every Docker image in deps. An unresolved ${VAR} tag, a malformed name, a refused pull or a
 failed scan leaves vulns None (not checked), never 'none known'. Each image:tag is looked up once per run, several at a time."""
 rows=[]
 for d in deps:
  if d.get('ecosystem')!='docker':continue
  name,tag=d['name'],str(d.get('version') or 'latest')
  if not NAME.fullmatch(name) or '..' in name or not TAG.fullmatch(tag):
   if '$' not in tag:log(f'WARN image reference not checked: {name}:{tag}')
   continue
  rows.append((d,(name,tag)))
 todo=sorted({k for _,k in rows if k not in cache})
 with ThreadPoolExecutor(max_workers=workers) as ex:
  for k,res in zip(todo,ex.map(lambda k:lookup(*k,tags_of,scan,log),todo)):cache[k]=res
 for d,k in rows:d.update({x:(dict(v) if isinstance(v,dict) else v) for x,v in cache[k].items()})
