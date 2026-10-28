"""Scanning a Docker image with osv-scanner, and reading its license from its labels."""
import json, os, re, shutil, subprocess
from common.log import warn
from common.proc import child_env
from common.versions import normal
from stackinfo.lookups.osv import SEVERITIES, severity as osv_severity
MAX_ITEMS=50   # postgres alone has hundreds; the counts stay exact, the list keeps the worst
SCAN_TIMEOUT=900

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
DOCKER_TIMEOUT=60
def scan(ref,run=subprocess.run,binary=None,docker=shutil.which('docker')):
 """Pull the image, then let osv-scanner read it. Pulling first matters: osv-scanner uses a copy that is already on the machine,
 and a runner can ship stale cached images, which would be reported as today's tag. An image that was not on the machine before
 is removed again, so a run over dozens of images does not fill the disk. The pull goes through the docker daemon, which resolves
 the registry's name itself: the public-host checks above cover the registry API calls, not this pull."""
 binary=binary or os.getenv('OSV_SCANNER') or shutil.which('osv-scanner')
 if not binary:raise RuntimeError('osv-scanner is not installed')
 env=child_env()
 had=bool(docker) and run([docker,'image','inspect',ref],capture_output=True,env=env,timeout=DOCKER_TIMEOUT).returncode==0
 labels={}
 try:
  if docker:
   pull=run([docker,'pull','-q',ref],capture_output=True,text=True,env=env,timeout=SCAN_TIMEOUT)
   if pull.returncode!=0:
    last=(pull.stderr or '').strip().splitlines()
    raise RuntimeError(f'docker pull failed: {last[-1][:150] if last else "no output"}')
  p=run([binary,'scan','image','--format','json',ref],capture_output=True,text=True,timeout=SCAN_TIMEOUT,env=env)
  if docker:labels=_labels(run([docker,'image','inspect','--format','{{json .Config.Labels}}',ref],capture_output=True,text=True,env=env,timeout=DOCKER_TIMEOUT))
 finally:
  if docker and not had:
   try:run([docker,'image','rm','-f',ref],capture_output=True,env=env,timeout=DOCKER_TIMEOUT)
   except Exception as e:warn(f'WARN could not remove image {ref}: {e}')   # cleanup must not hide the scan's own error
 if p.returncode==128:return {**summarize([]),'labels':labels}   # no packages found in the image
 if p.returncode not in (0,1):
  last=(p.stderr or '').strip().splitlines()
  raise RuntimeError(f'osv-scanner exit {p.returncode}: {last[-1][:150] if last else "no output"}')
 if not (p.stdout or '').strip():raise RuntimeError('osv-scanner printed no result')   # exit 1 means findings, so empty output is an error, not a clean image
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
REPO=re.compile(r'(?!\.)[A-Za-z0-9_.-]+/(?!\.)[A-Za-z0-9_.-]+')   # no x/. or x/..
GITHUB_REPO=re.compile(r'(?:https?://|git@)?github\.com[/:]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?(?:[#?].*)?')
def image_license(labels,repo_license):
 """(license, where): the image's own license label, else the license of the GitHub repo its source label names, else (None, None).
 repo_license('owner/repo') gives that repo's SPDX id."""
 lic=next((labels[k].strip() for k in LABEL_LICENSE if labels.get(k,'').strip()),None)
 if lic:return SPDX.get(lic.lower(),lic),'label'
 src=next((labels[k].strip() for k in LABEL_SOURCE if labels.get(k,'').strip()),'')
 m=GITHUB_REPO.fullmatch(src)
 if m and REPO.fullmatch(m.group(1)):
  lic=repo_license(m.group(1))
  if lic:return lic,'source'
 return None,None
