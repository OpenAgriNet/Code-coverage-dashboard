"""Why a dependency's latest version, license or vulnerability check is empty. Every empty value gets a reason, so the page never
shows a bare blank: state 'na' when the value does not exist for this dependency, 'nil' when it exists but could not be found."""
import re
from common.versions import clean_version
from stackinfo import settings

LOOKED=('npm','python','golang')
REGISTRY={'npm':'npm','python':'PyPI','golang':'the Go module proxy'}

def _local(d):
 return d.get('ecosystem')=='githubAction' and d.get('name','').startswith('./')
def _var(d):
 return '$' in str(d.get('version') or '')
def latest_reason(d,err):
 eco=d.get('ecosystem')
 if _local(d):return 'na','An action inside this repository: it has no releases'
 if eco=='docker':
  if _var(d):return 'nil','The tag is an unresolved ${VAR}: no compose default or .env example sets it'
  if err:return 'nil',f'Registry lookup failed: {err}'
  if d.get('latest_of')=='floating':return 'nil','The floating tag matches none of the newest 30 version tags in the registry, so its version is unknown'
  return 'nil','The registry lists no tag of the same shape as this one'
 if eco=='terraform':
  return 'nil',f'Provider registry lookup failed: {err}' if err else 'The provider registry lists no stable release'
 if eco=='githubRelease':
  return 'nil',f'GitHub lookup failed: {err}' if err else 'The repository publishes no releases or version tags'
 if eco=='githubAction':
  if err:return 'nil',f'GitHub lookup failed: {err}'
  return 'nil','The action repository publishes no releases or version tags'
 if eco in LOOKED:
  if d.get('license_of')=='error' or err:return 'nil',f'deps.dev lookup failed{": "+err if err else ""}'
  if d.get('license_of')=='not found':return 'nil',f'Not published on {REGISTRY[eco]} (deps.dev has no record): installed from a URL, Git or a private index'
  return 'nil','deps.dev lists no stable release'
 return 'nil','Latest version is not looked up for this ecosystem'
def license_reason(d,err):
 """(state, why, kind). kind 'none' means every place that could state a license was read and none does: the policy's
 no_license class applies to it. 'error', 'off' and 'na' are not a missing license."""
 eco=d.get('ecosystem')
 if _local(d):return 'na','An action inside this repository, not a published package','na'
 if eco=='docker':
  if err:return 'nil',f'The image could not be read, so its labels are unknown: {err}','error'
  return 'nil',('No license found: the image has no license label, its source label names no GitHub repository, config/repos.json '
   'gives none (dependencies.image_licenses or image_sources), and no package inside it is named like the image'),'none'
 if d.get('license_of')=='error':return 'nil',f'Lookup failed{": "+err if err else ""}; this is not a missing license','error'
 if d.get('license_of')=='not found':return 'nil',f'No license found: not published on {REGISTRY.get(eco,"its registry")}, and no source repository is known','none'
 return 'nil','No license found: neither the registry nor the source repository states a license','none'
def vulns_reason(d,err):
 eco=d.get('ecosystem')
 if _local(d):return 'na','An action inside this repository, not a published package'
 if _var(d):return 'nil','The version is an unresolved ${VAR}, so there is nothing to check'
 if err:return 'nil',('Scan failed: ' if eco=='docker' else 'Lookup failed: ')+err
 if eco=='githubAction':return 'nil','Pinned to a branch or to a commit no release tag points at, so no version to check'
 if eco=='terraform':return 'nil','No public vulnerability database (OSV, GitHub advisories) covers Terraform providers'
 if eco=='githubRelease':return 'nil','Installed from a GitHub release and not a Go module, so no vulnerability database can be asked about it'
 if eco in LOOKED:
  if not clean_version(d.get('installed') or d.get('version')):return 'nil','No version to check: the manifest gives no version and no lockfile pins one'
  return 'nil','Not checked'
 return 'nil','Vulnerabilities are not checked for this ecosystem'
CHECK_OF={'docker':'images','githubAction':'actions','terraform':'terraform'}
def turned_off(d,col):
 """The dependencies.checks switch that is off and left this column empty, or None."""
 eco=d.get('ecosystem')
 if col=='vulns' and eco in LOOKED and not settings.check('vulnerabilities'):return 'vulnerabilities'
 name=CHECK_OF.get(eco)
 return name if name and not settings.check(name) else None
def reason(col,d,err):
 off=turned_off(d,col)
 if off:return 'nil',f'Not looked up: dependencies.checks.{off} is turned off in config/repos.json','off'
 got={'latest':latest_reason,'license':license_reason,'vulns':vulns_reason}[col](d,err)
 return got if len(got)==3 else (*got,None)
def explain(deps):
 """Set d['missing'] = {column: {'state': 'na'|'nil', 'why': text}} for every empty latest, license and vulns, from the
 errors the lookups left in d['errors'] (which is then removed)."""
 for d in deps:
  errs=d.pop('errors',None) or {};missing={}
  if not d.get('latest') and not (d.get('ecosystem')=='docker' and d.get('latest_of')=='floating' and d.get('resolved')):
   s,w,_=reason('latest',d,errs.get('latest'));missing['latest']={'state':s,'why':w}
  if not d.get('license'):
   s,w,k=reason('license',d,errs.get('license'));missing['license']={'state':s,'why':w,'kind':k}
  if d.get('vulns') is None:
   s,w,_=reason('vulns',d,errs.get('vulns'));missing['vulns']={'state':s,'why':w}
  if missing:d['missing']=missing
  else:d.pop('missing',None)
def short_error(e,limit=150):
 """The last line of an exception's text, without tokens or long URLs."""
 s=str(e).strip().splitlines()[-1] if str(e).strip() else type(e).__name__
 s=re.sub(r'(?i)(bearer|token)[=: ]+\S+',r'\1 [hidden]',s)
 return s[:limit]
