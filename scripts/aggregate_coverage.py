#!/usr/bin/env python3
"""Aggregate supported coverage reports from existing GitHub Actions artifacts."""
import io, json, os, re, sys, zipfile
from datetime import datetime, timezone
import requests
from repoconfig import load as load_config, resolve
from releasefind import find_versions
import xml.etree.ElementTree as ET
MAX_ARTIFACT_BYTES=100*1024*1024  # artifacts are read into memory
API='https://api.github.com'; ORG=os.getenv('GITHUB_ORG','OpenAgriNet'); TOKEN=os.getenv('GH_TOKEN'); CODECOV_TOKEN=os.getenv('CODECOV_TOKEN'); PROJECT_TOKEN=os.getenv('DPG_PROJECT_TOKEN')
CFG=load_config('config/repos.json'); S=requests.Session(); S.headers.update({'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
if TOKEN: S.headers['Authorization']='Bearer '+TOKEN

def api(path):
 r=S.get(API+path,timeout=45)
 if r.status_code==404:return None
 r.raise_for_status();return r.json()
def xml_pct(raw):
 try: root=ET.fromstring(raw)
 except Exception:return None
 for k in ('line-rate','lineRate'):
  if root.attrib.get(k) is not None:
   try:
    x=float(root.attrib[k]);return x*100 if x<=1 else x
   except ValueError:pass
 for c in root.findall('.//counter'):
  if c.attrib.get('type')=='LINE' and 'covered' in c.attrib and 'missed' in c.attrib:
   n=int(c.attrib['covered'])+int(c.attrib['missed']);return 100*int(c.attrib['covered'])/n if n else 100.0
 for n in root.iter():
  if n.tag.lower().endswith('metrics') and 'coveredstatements' in n.attrib and 'statements' in n.attrib:
   total=int(n.attrib['statements']);return 100*int(n.attrib['coveredstatements'])/total if total else 100.0
 return None
def parse(name,raw):
 low=name.lower()
 if low.endswith('.xml') and any(k in low for k in ('coverage','cobertura','clover','jacoco')):
  p=xml_pct(raw)
  if p is not None:return p,'XML'
 if low.endswith(('lcov.info','.lcov')):
  t=raw.decode('utf-8','replace');lf=re.findall(r'^LF:(\d+)$',t,re.M);lh=re.findall(r'^LH:(\d+)$',t,re.M)
  if lf and lh:
   n=sum(map(int,lf));return (100*sum(map(int,lh))/n if n else 100.0),'LCOV'
 if low.endswith('.json') and ('coverage' in low or 'summary' in low):
  try:o=json.loads(raw)
  except Exception:return None
  t=o.get('total',o);lines=t.get('lines',{}) if isinstance(t,dict) else {}
  if isinstance(lines,dict) and 'pct' in lines:return float(lines['pct']),'JSON lines'
  for k in ('line_coverage','lineCoverage','coverage'):
   if isinstance(t,dict) and isinstance(t.get(k),(int,float)):
    x=float(t[k]);return (x*100 if 0<=x<=1 else x),'JSON'
 if low.endswith(('.txt','.out')) and ('coverage' in low or 'coverprofile' in low):
  lines=[x.split() for x in raw.decode('utf-8','replace').splitlines() if x and not x.startswith('mode:')]
  if lines and all(len(x)>=3 for x in lines):
   try:
    total=sum(int(x[1]) for x in lines);hit=sum(int(x[1]) for x in lines if int(x[2])>0);return (100*hit/total if total else 100.0),'Go coverprofile'
   except Exception:pass
 return None
def codecov(repo,branch,sha=None):
 """Codecov totals for the latest uploaded commit on `branch`, or for commit `sha` when given."""
 h={'Accept':'application/json'}
 if CODECOV_TOKEN:h['Authorization']='Bearer '+CODECOV_TOKEN
 try:
  u=f'https://api.codecov.io/api/v2/github/{ORG}/repos/{repo}/totals/'
  q={'sha':sha} if sha else {'branch':branch}
  r=requests.get(u,headers=h,params=q,timeout=45)
  if r.status_code in (401,403) and CODECOV_TOKEN:r=requests.get(u,headers={'Accept':'application/json'},params=q,timeout=45)
  if r.status_code!=200:return None
  j=r.json();t=j.get('totals') or {}
  if t.get('coverage') is None:return None
  m=re.search(r'/commit/([0-9a-f]{7,40})',j.get('commit_file_url') or '')
  return {'coverage':round(float(t['coverage']),2),'files':t.get('files'),'lines':t.get('lines'),'hits':t.get('hits'),'misses':t.get('misses'),'partials':t.get('partials'),'commit':m.group(1) if m else None,'report_url':f'https://app.codecov.io/github/{ORG}/{repo}/tree/{branch}'}
 except Exception as e:print(f'WARN codecov {repo}@{branch}: {e}',file=sys.stderr);return None
def commit_date(repo,sha):
 c=api(f'/repos/{ORG}/{repo}/commits/{sha}') if sha else None
 return ((c or {}).get('commit') or {}).get('committer',{}).get('date')
def default_branch(repo):
 return (api(f'/repos/{ORG}/{repo}') or {}).get('default_branch') or 'main'
def resolve_branch(repo,branch):
 """(branch, exists). None means the repo's default branch."""
 if not branch:return default_branch(repo),True
 return branch,bool(api(f'/repos/{ORG}/{repo}/branches/{branch}'))
def inspect(t):
 """Coverage and security of one ref: a branch, or (when t['sha'] is set) a tagged commit, which has no live badges."""
 repo=t['name'];url=f'https://github.com/{ORG}/{repo}';sha=t.get('sha')
 branch,exists=(t['branch'],True) if sha else resolve_branch(repo,t.get('branch'))
 out={'repository':repo,'html_url':url,'dpg':'DPG' in t.get('tags',[]),'tags':t.get('tags',[]),'branch':branch,'ref_kind':'tag' if sha else 'branch','branch_exists':exists,
  'coverage':None,'coverage_source':'Branch not found','coverage_commit':None,'coverage_detail':None,
  'coverage_badge_url':None if sha else f'https://codecov.io/gh/{ORG}/{repo}/branch/{branch}/graph/badge.svg','measured_at':None,
  'security':{'state':'branch not found','run_url':None,'badge_url':None,'finished_at':None}}
 if not exists:return out
 m=branch_coverage(repo,branch,sha)
 out.update(coverage=m['coverage'],coverage_source=m['source'],coverage_commit=m['commit'],coverage_detail=m['detail'],measured_at=m['measured_at'],
  security=security_status(repo,branch,t.get('security_workflow','security.yml'),sha))
 return out
def branch_coverage(repo,branch,sha=None):
 """Coverage of one branch (or of commit `sha`): Codecov first, else artifacts of the latest CI run there."""
 out={'branch':branch,'coverage':None,'source':None,'commit':None,'detail':None,'measured_at':None,'workflow_conclusion':None,'workflow_url':None}
 cc=codecov(repo,branch,sha)
 if cc:out.update(coverage=cc['coverage'],source='Codecov',commit=cc['commit'],detail={k:cc[k] for k in ('files','lines','hits','misses','partials','report_url')},measured_at=commit_date(repo,cc['commit']))
 try:
  d=api(f'/repos/{ORG}/{repo}/actions/runs?{"head_sha="+sha if sha else "branch="+branch}&per_page=100') or {};names=[n.lower() for n in CFG.get('workflow_names',[])]
  runs=sorted([r for r in d.get('workflow_runs',[]) if r.get('status')=='completed' and (not names or r.get('name','').lower() in names)],key=lambda r:r.get('updated_at',''),reverse=True)
  run=next((r for r in runs if r.get('conclusion')=='success'),runs[0] if runs else None)
  if not run:
   out['workflow_conclusion']='no completed run'
   if not cc:out['source']=f'No Codecov upload or CI run on {branch}'
   return out
  out.update(workflow_conclusion=run.get('conclusion'),workflow_url=run.get('html_url'))
  if cc:return out
  out.update(commit=run.get('head_sha'),measured_at=run.get('updated_at'))
  arts=(api(f"/repos/{ORG}/{repo}/actions/runs/{run['id']}/artifacts?per_page=100") or {}).get('artifacts',[])
  hints=CFG.get('artifact_name_hints',[])
  for a in arts:
   if a.get('expired') or a.get('size_in_bytes',0)>MAX_ARTIFACT_BYTES or (hints and not any(h.lower() in a.get('name','').lower() for h in hints)):continue
   try:
    zresp=S.get(f"{API}/repos/{ORG}/{repo}/actions/artifacts/{a['id']}/zip",timeout=90);zresp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(zresp.content)) as z:
     for member in z.namelist():
      if member.endswith('/'):continue
      val=parse(member,z.read(member))
      if val:out.update(coverage=round(val[0],2),source=f'{val[1]} · {a["name"]}',detail={'report_url':run.get('html_url'),'file':member});return out
   except Exception as e:print(f'WARN {repo}@{branch}/{a.get("name")}: {e}',file=sys.stderr)
  out['source']=f'No coverage report in latest {branch} run'
 except Exception as e:out.update(workflow_conclusion='error',source=str(e)[:180]);print(f'ERROR {repo}@{branch}: {e}',file=sys.stderr)
 return out
def security_status(repo,branch,workflow,sha=None):
 """Latest completed run of the security workflow on `branch`, or on commit `sha` (no live badge for a commit)."""
 out={'state':'no workflow','run_url':None,'badge_url':None,'finished_at':None}
 if not api(f'/repos/{ORG}/{repo}/actions/workflows/{workflow}'):return out
 if not sha:out['badge_url']=f'https://github.com/{ORG}/{repo}/actions/workflows/{workflow}/badge.svg?branch={branch}'
 runs=(api(f'/repos/{ORG}/{repo}/actions/workflows/{workflow}/runs?{"head_sha="+sha if sha else "branch="+branch}&status=completed&per_page=1') or {}).get('workflow_runs',[])
 if not runs:out['state']='no runs';return out
 r=runs[0];out.update(state='passing' if r.get('conclusion')=='success' else 'failing',run_url=r.get('html_url'),finished_at=r.get('updated_at'))
 return out
def safe_inspect(t):
 """inspect(), but one repo's API failure becomes an 'unknown' row instead of stopping the whole refresh."""
 try:return inspect(t)
 except Exception as e:
  print(f'ERROR {t["name"]}@{t.get("branch")}: {e}',file=sys.stderr)
  return {'repository':t['name'],'html_url':f'https://github.com/{ORG}/{t["name"]}','dpg':'DPG' in t.get('tags',[]),'tags':t.get('tags',[]),'branch':t.get('branch') or 'default','branch_exists':None,
   'coverage':None,'coverage_source':f'Error: {str(e)[:120]}','coverage_commit':None,'coverage_detail':None,'coverage_badge_url':None,'measured_at':None,
   'security':{'state':'unknown','run_url':None,'badge_url':None,'finished_at':None}}
def release_group(t):
 """Every release version of one repo, each measured, or None when releases are off or none were found.
 The default pick is the newest stable version (the newest one if all are pre-releases)."""
 rc=t.get('releases')
 if not rc:return None
 try:found=find_versions(ORG,t['name'],rc,api)
 except Exception as e:print(f'ERROR {t["name"]} releases: {e}',file=sys.stderr);return None
 recs=[]
 for v in found['versions']:
  rec=safe_inspect({**t,'branch':v['ref'],'sha':v['sha'] if v['ref_kind']=='tag' else None})
  rec.update(version=v['version'],ref_kind=v['ref_kind'],kinds=v['kinds'],prerelease=v['prerelease'],published_at=v['published_at'],sha=v['sha'])
  recs.append(rec)
 if not recs:return None
 return {'repository':t['name'],'html_url':f'https://github.com/{ORG}/{t["name"]}','dpg':'DPG' in t.get('tags',[]),'tags':t.get('tags',[]),
  'default':next((r['version'] for r in recs if not r['prerelease']),recs[0]['version']),'not_measured':found['total']-len(recs),'versions':recs}
def collect(targets):
 """Configured-branch view, default-branch (main) view, and per-repo release versions for every target."""
 dev,main,rel=[],[],[]
 for t in targets:
  r=safe_inspect(t);dev.append(r)
  try:d=default_branch(t['name'])
  except Exception as e:print(f'ERROR {t["name"]} default branch: {e}',file=sys.stderr);d=None
  main.append(r if d is None or r['branch']==d else safe_inspect({**t,'branch':d}))
  g=release_group(t)
  if g:rel.append(g)
 return {'repositories':dev,'main':main,'releases':rel}
def main():
 targets=resolve(CFG,ORG,api,PROJECT_TOKEN)
 d=collect(targets);results=d['repositories']
 os.makedirs('data',exist_ok=True)
 with open('data/coverage.json','w',encoding='utf-8') as f:json.dump({'organization':ORG,'generated_at':datetime.now(timezone.utc).isoformat(),**d},f,indent=2);f.write('\n')
 print(f"Wrote data/coverage.json for {len(results)} repos; coverage found for {sum(r['coverage'] is not None for r in results)}.")
if __name__=='__main__':main()
