"""Known vulnerabilities of dependencies, from OSV.dev (Google's open vulnerability database; public API, no key or login).
Only package names and versions are sent. They are checked at the declared version: the lowest one a range such as ^5.0.0 allows."""
import re, sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
RETRY=Retry(total=3,backoff_factor=1,status_forcelist=(429,500,502,503,504),allowed_methods=None)  # public APIs rate-limit and blip; one retry round hides that
from .versions import clean_version
from .reasons import short_error
OSV='https://api.osv.dev/v1'
ECOSYSTEMS={'npm':'npm','python':'PyPI','golang':'Go'}  # stack-analyser ecosystem -> OSV ecosystem; docker and actions are not covered
BATCH=500
SEVERITIES=('LOW','MODERATE','HIGH','CRITICAL')
S=requests.Session(); DETAILS={}
S.mount('https://',HTTPAdapter(max_retries=RETRY))

def post(path,body):
 r=S.post(f'{OSV}{path}',json=body,timeout=60);r.raise_for_status();return r.json()
def get(path):
 r=S.get(f'{OSV}{path}',timeout=30);r.raise_for_status();return r.json()
PRE=re.compile(r'[-.]?(?:a|b|c|rc|dev|alpha|beta|pre)\d*',re.I)
def vkey(v):
 """Sort key: the release numbers (padded to three), then a final release above its own pre-releases (2.0.0-rc.1 < 2.0.0)."""
 m=re.match(r'v?(\d+(?:\.\d+)*)(.*)$',str(v).strip())
 if not m:return ((0,0,0),0)
 nums=tuple(int(x) for x in m.group(1).split('.'))
 return (nums+(0,)*(3-len(nums)),0 if PRE.search(m.group(2)) else 1)
def normal(name):
 return re.sub(r'[-_.]+','-',name).lower()
def fixed_version(vuln,eco,name,version):
 """Lowest fixed version above `version` in this vulnerability's entries for the package, or None when nothing fixes it.
 Commit-hash (GIT) ranges are ignored."""
 cur=vkey(version);best=None
 for a in vuln.get('affected',[]):
  p=a.get('package') or {}
  if p.get('ecosystem')!=eco or normal(p.get('name',''))!=normal(name):continue
  for rg in a.get('ranges',[]):
   if rg.get('type')=='GIT':continue
   for e in rg.get('events',[]):
    f=e.get('fixed')
    if f and vkey(f)>cur and (best is None or vkey(f)<vkey(best)):best=f
 return best
def severity(vuln):
 s=str((vuln.get('database_specific') or {}).get('severity','')).upper()
 return 'MODERATE' if s=='MEDIUM' else s if s in SEVERITIES else 'UNKNOWN'
def item(vuln,eco,name,version):
 cve=next((a for a in vuln.get('aliases',[]) if a.startswith('CVE-')),None)
 return {'id':vuln['id'],'cve':cve,'summary':vuln.get('summary') or (vuln.get('details') or '').split('\n')[0][:160],'severity':severity(vuln),
  'fixed':fixed_version(vuln,eco,name,version),'url':f'https://osv.dev/vulnerability/{vuln["id"]}'}
def details(vid,fetch):
 if vid not in DETAILS:DETAILS[vid]=fetch(f'/vulns/{vid}')
 return DETAILS[vid]
def is_exact(declared):
 """A pin (1.2.3, v1.2.3, ==1.2.3, =1.2.3) rather than a range (^1.2.3, >=1, 1.x)."""
 d=re.sub(r'^={1,2}','',str(declared).strip())
 return bool(re.match(r'v?\d',d)) and not any(c in d for c in '^~<>=*|, x')
def summarize(items):
 fixes=[i['fixed'] for i in items if i['fixed']]
 rank=lambda i:SEVERITIES.index(i['severity']) if i['severity'] in SEVERITIES else -1
 return {'count':len(items),'severity':max(items,key=rank)['severity'] if items else None,'fixed_in':max(fixes,key=vkey) if fixes else None,
  'unfixed':sum(1 for i in items if not i['fixed']),'items':items}
def annotate(deps,post=post,fetch=get,log=lambda m:print(m,file=sys.stderr)):
 """Add 'vulns' to every dependency dict. None means not checked (Docker image, Action, unknown version, or the lookup failed);
 otherwise {checked_version, exact, count, severity, fixed_in, unfixed, items}. fixed_in is the one version that fixes every fixable item."""
 todo=[]
 for d in deps:
  d['vulns']=None;eco=ECOSYSTEMS.get(d['ecosystem']);v=clean_version(d.get('installed') or d['version'])  # the lockfile's version beats a range
  if eco and v:todo.append((d,eco,v))
 for i in range(0,len(todo),BATCH):
  chunk=todo[i:i+BATCH]
  try:
   results=post('/querybatch',{'queries':[{'package':{'name':d['name'],'ecosystem':eco},'version':v} for d,eco,v in chunk]})['results']
   for (d,eco,v),res in zip(chunk,results):
    try:  # one failing advisory lookup leaves only this dependency unchecked, never a half-filled result
     seen=set();items=[]
     for vid in sorted(x['id'] for x in res.get('vulns',[])):
      vuln=details(vid,fetch)
      ids={vuln['id'],*vuln.get('aliases',[])}
      if vuln.get('withdrawn') or ids&seen:continue  # withdrawn, or the same advisory under another id (GHSA/PYSEC/CVE)
      seen|=ids;items.append(item(vuln,eco,d['name'],v))
     d['vulns']={'checked_version':v,'exact':bool(d.get('installed')) or is_exact(d['version']),**summarize(items)}
    except Exception as e:d.setdefault('errors',{})['vulns']=f'OSV: {short_error(e)}';log(f'WARN OSV advisory lookup failed for {d["name"]}: {e}')
  except Exception as e:
   for d,_,_ in chunk:d.setdefault('errors',{})['vulns']=f'OSV: {short_error(e)}'
   log(f'WARN OSV lookup failed for {len(chunk)} dependencies: {e}')
