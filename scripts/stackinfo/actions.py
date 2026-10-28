"""GitHub Actions: the exact version behind a tag such as v4, the latest release, the action repo's license and its known
vulnerabilities, all from the GitHub API (GH_TOKEN). OSV holds Actions advisories but cannot match them to a version, so
GitHub's advisory database is used instead."""
import re, sys
import aggregate_coverage as ac
from .vulns import summarize, vkey
from .reasons import short_error
SEV={'low':'LOW','medium':'MODERATE','moderate':'MODERATE','high':'HIGH','critical':'CRITICAL'}
SHA=re.compile(r'[0-9a-f]{40}')
FULL=re.compile(r'v?\d+\.\d+\.\d+.*')
FLOAT=re.compile(r'v?\d+(?:\.\d+)?')
RELEASE=re.compile(r'v?\d+(?:\.\d+)*')   # a plain release tag: no -beta, no 'nightly'
# names and refs come from workflow files in the tracked repos, so only well-formed ones reach a GitHub API path
NAME=re.compile(r'(?!\.)[A-Za-z0-9_.-]+/(?!\.)[A-Za-z0-9_.-]+')
REF=re.compile(r'[A-Za-z0-9_.-]+')

def repo_of(name):
 """'github/codeql-action/init' -> 'github/codeql-action'."""
 return '/'.join(name.split('/')[:2])
def resolve(repo,ref,api):
 """The release a ref runs: a full tag as is, a floating tag (v4, v4.2) as its newest release tag, a commit as the tag on it.
 None when the ref is not a version (a branch, or a commit no tag points at)."""
 if FULL.fullmatch(ref):return ref
 if SHA.fullmatch(ref):
  return next((t['name'] for t in api(f'/repos/{repo}/tags?per_page=100') or [] if t.get('commit',{}).get('sha')==ref),None)
 if not FLOAT.fullmatch(ref):return None
 # the trailing dot keeps v4 from matching v40
 tags=[r['ref'].rsplit('/',1)[-1] for r in api(f'/repos/{repo}/git/matching-refs/tags/{ref}.') or []]
 tags=[t for t in tags if RELEASE.fullmatch(t)]
 return max(tags,key=vkey) if tags else ref
def latest(repo,api):
 """Tag of the latest release; the highest release tag when the repo publishes no releases."""
 rel=api(f'/repos/{repo}/releases/latest')
 if rel and rel.get('tag_name'):return rel['tag_name']
 tags=[t['name'] for t in api(f'/repos/{repo}/tags?per_page=100') or [] if RELEASE.fullmatch(t['name'])]
 return max(tags,key=vkey) if tags else None
def advisories(repo,version,api):
 """Known vulnerabilities of repo@version, in the item shape vulns.py gives OSV advisories."""
 out=[]
 for adv in api(f'/advisories?ecosystem=actions&affects={repo}@{version.lstrip("v")}&per_page=100') or []:
  if adv.get('withdrawn_at'):continue
  fixed=next((v.get('first_patched_version') for v in adv.get('vulnerabilities') or [] if (v.get('package') or {}).get('name','').lower()==repo.lower()),None)
  if isinstance(fixed,dict):fixed=fixed.get('identifier')
  out.append({'id':adv['ghsa_id'],'cve':adv.get('cve_id'),'summary':adv.get('summary') or '','severity':SEV.get(str(adv.get('severity')).lower(),'UNKNOWN'),
   'fixed':fixed,'url':adv.get('html_url') or f'https://github.com/advisories/{adv["ghsa_id"]}'})
 return out
def license_of(repo,api):
 lic=(api(f'/repos/{repo}/license') or {}).get('license')
 if not lic:return None
 return lic.get('spdx_id') if lic.get('spdx_id') not in (None,'NOASSERTION') else 'Other'
def lookup(repo,ref,api):
 exact=resolve(repo,ref,api)
 out={'latest':latest(repo,api),'license':license_of(repo,api),'license_of':'repo','vulns':None}
 if exact and exact!=ref:out['resolved']=exact
 if exact:out['vulns']={'checked_version':exact,'exact':True,**summarize(advisories(repo,exact,api))}
 return out
CACHE={}
def annotate(deps,api=ac.api,cache=CACHE,log=lambda m:print(m,file=sys.stderr)):
 """Fill latest, license and vulns of every published action in deps (local ./ actions and other ecosystems are left alone).
 One lookup per action and ref per run; a failed lookup leaves vulns None (not checked) and marks license_of 'error'."""
 for d in deps:
  if d.get('ecosystem')!='githubAction' or d['name'].startswith(('./','docker://')):continue
  key=(repo_of(d['name']),str(d.get('version') or ''))
  if not NAME.fullmatch(key[0]) or '..' in key[0] or not REF.fullmatch(key[1]):log(f'WARN action reference not checked: {d["name"]}@{key[1]}');continue
  if key not in cache:
   try:cache[key]=lookup(*key,api)
   except Exception as e:
    m=f'GitHub: {short_error(e)}';cache[key]={'license_of':'error','vulns':None,'errors':{'latest':m,'license':m,'vulns':m}}
    log(f'WARN GitHub lookup failed for action {d["name"]}@{key[1]}: {e}')
  d.update({k:(dict(v) if isinstance(v,dict) else v) for k,v in cache[key].items()})
