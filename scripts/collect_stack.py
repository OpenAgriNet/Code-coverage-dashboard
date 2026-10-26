#!/usr/bin/env python3
"""Stack, dependencies and licenses per repo: specfy/stack-analyser on a shallow clone, deps.dev for each dependency's license."""
import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timezone
from urllib.parse import quote
import requests
import aggregate_coverage as ac
ANALYSER='@specfy/stack-analyser@1.27.6'; DEPSDEV='https://api.deps.dev/v3/systems'
SYSTEMS={'npm':'NPM','python':'PYPI','golang':'GO'}  # stack-analyser ecosystem -> deps.dev system; docker/githubAction have no license data there
D=requests.Session()
SAFE_ENV=('PATH','HOME','TMPDIR','TEMP','TMP','LANG','LC_ALL','XDG_CACHE_HOME','RUNNER_TEMP')

def child_env():
 """Environment for git and npx: an allowlist, so third-party npm code never sees GH_TOKEN, DPG_PROJECT_TOKEN or the Actions OIDC request token."""
 env={k:os.environ[k] for k in SAFE_ENV if k in os.environ}
 env.update(npm_config_ignore_scripts='true',GIT_TERMINAL_PROMPT='0')
 return env
def analyse(repo,branch):
 """Raw stack-analyser output (flat) for a shallow clone of repo@branch."""
 env=child_env()
 with tempfile.TemporaryDirectory() as tmp:
  src=os.path.join(tmp,'src')
  subprocess.run(['git','clone','-q','--depth','1','-b',branch,f'https://github.com/{ac.ORG}/{repo}.git',src],check=True,timeout=300,env=env)
  # the CLI joins -o onto the working directory, so pass a bare file name
  subprocess.run(['npx','--yes',ANALYSER,src,'--flat','-o','out.json'],cwd=tmp,check=True,timeout=600,stdout=subprocess.DEVNULL,env=env)
  return json.load(open(os.path.join(tmp,'out.json'),encoding='utf-8'))
def summarize(raw):
 """Languages by file count, tech keys, and deduplicated [ecosystem, name, version] dependencies."""
 langs=sorted((raw.get('languages') or {}).items(),key=lambda x:(-x[1],x[0]))
 seen=set();deps=[]
 for e,n,v in raw.get('dependencies') or []:
  if (e,n,v) in seen:continue
  seen.add((e,n,v));deps.append([e,n,v])
 return {'languages':langs,'techs':sorted(set(raw.get('techs') or [])),'dependencies':sorted(deps,key=lambda d:(d[0],d[1].lower()))}
def clean_version(v):
 """'^1.2.6' -> '1.2.6', '>=2.0,<3' -> '2.0'; None for 'latest', '*' or ${VARS}."""
 m=re.search(r'v?\d+(?:\.[0-9A-Za-z-]+)*',str(v or '').split(',')[0])
 return m.group(0) if m and '$' not in str(v) else None
def depsdev(path):
 r=D.get(f'{DEPSDEV}/{path}',timeout=30)
 if r.status_code==404:return None
 r.raise_for_status();return r.json()
PRERELEASE=re.compile(r'-|(?:a|b|c|rc|dev|alpha|beta|pre)\.?\d*$',re.I)  # semver '-rc.1', PEP 440 'b1'/'rc2'/'.dev6'; '.post1' stays stable
def latest_stable(versions):
 """deps.dev's default version, unless it is a pre-release (PyPI often marks e.g. 1.0.0.dev6 default); then the newest stable one."""
 stable=lambda v:not PRERELEASE.search(v['versionKey']['version'])
 d=next((v for v in versions if v.get('isDefault')),None)
 if d and stable(d):return d['versionKey']['version']
 s=max((v for v in versions if stable(v)),key=lambda v:v.get('publishedAt') or '',default=None)
 return (s or d or {}).get('versionKey',{}).get('version')
def dep_info(eco,name,version,fetch=None):
 """License and latest version from deps.dev. license_of says which version the license came from."""
 fetch=fetch or depsdev
 out={'ecosystem':eco,'name':name,'version':version,'latest':None,'license':None,'license_of':None}
 system=SYSTEMS.get(eco)
 if not system:return out
 try:
  pkg=fetch(f'{system}/packages/{quote(name,safe="")}')
  if not pkg:out['license_of']='not found';return out
  out['latest']=latest_stable(pkg.get('versions',[]))
  want=clean_version(version)
  if system=='GO' and want and not want.startswith('v'):want='v'+want
  for v,tag in ((want,'pinned'),(out['latest'],'latest')):
   info=fetch(f'{system}/packages/{quote(name,safe="")}/versions/{quote(v,safe="")}') if v else None
   if info:out.update(license=' OR '.join(info.get('licenses') or []) or None,license_of=tag);break
 except Exception as e:print(f'WARN deps.dev {eco}/{name}: {e}',file=sys.stderr)
 return out
def repo_license(repo):
 """SPDX id of the repo's own LICENSE file, 'Other' if GitHub can't classify it, None if there is none."""
 lic=(ac.api(f'/repos/{ac.ORG}/{repo}/license') or {}).get('license')
 if not lic:return None
 return lic.get('spdx_id') if lic.get('spdx_id') not in (None,'NOASSERTION') else 'Other'
def stack_record(t,analyse=analyse,info=dep_info):
 repo=t['name'];branch=t.get('branch') or ac.default_branch(repo)
 out={'repository':repo,'html_url':f'https://github.com/{ac.ORG}/{repo}','dpg':repo in ac.CFG.get('dpg_repositories',[]),'branch':branch,
  'license':None,'languages':[],'techs':[],'dependencies':[],'error':None}
 try:out['license']=repo_license(repo)
 except Exception as e:print(f'WARN license {repo}: {e}',file=sys.stderr)
 try:
  s=summarize(analyse(repo,branch))
  out.update(languages=s['languages'],techs=s['techs'],dependencies=[info(*d) for d in s['dependencies']])
 except Exception as e:out['error']=str(e)[:180];print(f'ERROR stack {repo}@{branch}: {e}',file=sys.stderr)
 return out
def main():
 dpg=ac.dpg_project_repos()
 if dpg is None:dpg=ac.CFG.get('dpg_repositories',[])
 ac.CFG['dpg_repositories']=dpg
 rows=[stack_record(t) for t in ac.repo_targets(ac.CFG,dpg)]
 os.makedirs('data',exist_ok=True)
 with open('data/stack.json','w',encoding='utf-8') as f:json.dump({'organization':ac.ORG,'generated_at':datetime.now(timezone.utc).isoformat(),'analyser':ANALYSER,'repositories':rows},f,indent=2);f.write('\n')
 print(f"Wrote data/stack.json for {len(rows)} repos; {sum(len(r['dependencies']) for r in rows)} dependencies.")
if __name__=='__main__':main()
