"""License and latest version of a dependency from deps.dev."""
import sys
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .versions import clean_version, latest_stable
DEPSDEV='https://api.deps.dev/v3/systems'
SYSTEMS={'npm':'NPM','python':'PYPI','golang':'GO'}  # stack-analyser ecosystem -> deps.dev system; docker/githubAction have no license data there
D=requests.Session()
D.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=(429,500,502,503,504))))

def fetch(path):
 r=D.get(f'{DEPSDEV}/{path}',timeout=30)
 if r.status_code==404:return None
 r.raise_for_status();return r.json()
def dep_info(eco,name,version,fetch=fetch):
 """License and latest version from deps.dev. license_of says which version the license came from."""
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
 except Exception as e:out['license_of']='error';print(f'WARN deps.dev {eco}/{name}: {e}',file=sys.stderr)  # 'error' so a lookup failure is not shown as 'no license'
 return out
