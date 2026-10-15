#!/usr/bin/env python3
"""Aggregate supported coverage reports from existing GitHub Actions artifacts."""
import io, json, os, re, sys, zipfile
from datetime import datetime, timedelta, timezone
import requests
import xml.etree.ElementTree as ET
API='https://api.github.com'; ORG=os.getenv('GITHUB_ORG','OpenAgriNet'); TOKEN=os.getenv('GH_TOKEN'); CODECOV_TOKEN=os.getenv('CODECOV_TOKEN')
CFG=json.load(open('config/repos.json',encoding='utf-8')); S=requests.Session(); S.headers.update({'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
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
def codecov(repo,branch):
 """Codecov totals for the latest uploaded commit on `branch`."""
 h={'Accept':'application/json'}
 if CODECOV_TOKEN:h['Authorization']='Bearer '+CODECOV_TOKEN
 try:
  u=f'https://api.codecov.io/api/v2/github/{ORG}/repos/{repo}/totals/'
  r=requests.get(u,headers=h,params={'branch':branch},timeout=45)
  if r.status_code in (401,403) and CODECOV_TOKEN:r=requests.get(u,headers={'Accept':'application/json'},params={'branch':branch},timeout=45)
  if r.status_code!=200:return None
  j=r.json();t=j.get('totals') or {}
  if t.get('coverage') is None:return None
  m=re.search(r'/commit/([0-9a-f]{7,40})',j.get('commit_file_url') or '')
  return {'coverage':round(float(t['coverage']),2),'files':t.get('files'),'lines':t.get('lines'),'hits':t.get('hits'),'misses':t.get('misses'),'partials':t.get('partials'),'commit':m.group(1) if m else None,'report_url':f'https://app.codecov.io/github/{ORG}/{repo}/tree/{branch}'}
 except Exception as e:print(f'WARN codecov {repo}@{branch}: {e}',file=sys.stderr);return None
def commit_date(repo,sha):
 c=api(f'/repos/{ORG}/{repo}/commits/{sha}') if sha else None
 return ((c or {}).get('commit') or {}).get('committer',{}).get('date')
def details(repo,branch):
 """Extra repo details: latest merged PR and default-branch activity."""
 out={'last_merged_pr':None,'main_last_commit':None,'main_commits_recent':None,'activity_days':CFG.get('activity_days',30)}
 try:
  pulls=[p for p in (api(f'/repos/{ORG}/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=50') or []) if p.get('merged_at')]
  if pulls:
   p=max(pulls,key=lambda p:p['merged_at']);out['last_merged_pr']={'number':p['number'],'title':p['title'],'url':p['html_url'],'merged_at':p['merged_at'],'author':(p.get('user') or {}).get('login'),'base':(p.get('base') or {}).get('ref')}
  since=(datetime.now(timezone.utc)-timedelta(days=out['activity_days'])).strftime('%Y-%m-%dT%H:%M:%SZ')
  commits=api(f'/repos/{ORG}/{repo}/commits?sha={branch}&since={since}&per_page=100') or []
  out['main_commits_recent']=len(commits)
  last=commits[0] if commits else ((api(f'/repos/{ORG}/{repo}/commits?sha={branch}&per_page=1') or [None])[0])
  if last:out['main_last_commit']=((last.get('commit') or {}).get('committer') or {}).get('date')
 except Exception as e:print(f'WARN details {repo}: {e}',file=sys.stderr)
 return out
def default_branch(repo):
 return (api(f'/repos/{ORG}/{repo}') or {}).get('default_branch') or 'main'
def inspect(repo):
 url=f'https://github.com/{ORG}/{repo}';branch=default_branch(repo)
 devs=[b for b in CFG.get('dev_branch_names',['dev','develop','development']) if b!=branch and api(f'/repos/{ORG}/{repo}/branches/{b}')]
 m=branch_coverage(repo,branch)
 out={'owner':ORG,'repository':repo,'html_url':url,'dpg':repo in CFG.get('dpg_repositories',[]),'default_branch':branch,'dev_branches':devs,
  'coverage':m['coverage'],'coverage_source':m['source'],'coverage_branch':branch,'coverage_commit':m['commit'],'coverage_detail':m['detail'],'updated_at':m['measured_at'],
  'workflow_conclusion':m['workflow_conclusion'],'workflow_url':m['workflow_url'] or url+'/actions',
  'dev_coverage':branch_coverage(repo,devs[0]) if devs else None}
 out.update(details(repo,branch));return out
def branch_coverage(repo,branch):
 """Coverage of one branch: Codecov first, else artifacts of the latest CI run on that branch."""
 out={'branch':branch,'coverage':None,'source':None,'commit':None,'detail':None,'measured_at':None,'workflow_conclusion':None,'workflow_url':None}
 cc=codecov(repo,branch)
 if cc:out.update(coverage=cc['coverage'],source='Codecov',commit=cc['commit'],detail={k:cc[k] for k in ('files','lines','hits','misses','partials','report_url')},measured_at=commit_date(repo,cc['commit']))
 try:
  d=api(f'/repos/{ORG}/{repo}/actions/runs?branch={branch}&per_page=100') or {};names=[n.lower() for n in CFG.get('workflow_names',[])]
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
   if a.get('expired') or (hints and not any(h.lower() in a.get('name','').lower() for h in hints)):continue
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
def main():
 repos=CFG.get('repositories',[]);results=[inspect(r) for r in repos]
 os.makedirs('data',exist_ok=True)
 with open('data/coverage.json','w',encoding='utf-8') as f:json.dump({'organization':ORG,'generated_at':datetime.now(timezone.utc).isoformat(),'repositories':results},f,indent=2);f.write('\n')
 print(f"Wrote data/coverage.json for {len(results)} repos; coverage found for {sum(r['coverage'] is not None for r in results)}.")
if __name__=='__main__':main()
