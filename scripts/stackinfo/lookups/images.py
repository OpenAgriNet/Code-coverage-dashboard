"""Docker images: latest tag, the version behind a floating tag, vulnerabilities and license, each looked up once per run."""
from concurrent.futures import ThreadPoolExecutor
from common.log import warn
from common.safehttp import public_host
from stackinfo.rules.reasons import short_error
from stackinfo.lookups.registry import NAME, TAG, SHAPE, split, canonical, latest_like, tags_of, version_of
from stackinfo.lookups.imagescan import scan, image_license
from stackinfo.lookups.projects import project_license
from stackinfo import settings
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
 try:res=scan(f'{name}:{tag}')
 except Exception as e:errors['vulns']=errors['license']=short_error(e);log(f'WARN image scan failed for {name}:{tag}: {e}')
 else:
  labels=res.pop('labels',{})
  out['vulns']={'checked_version':tag,'exact':True,**res}
  try:lic,where=image_license(labels,license_of)
  except Exception as e:errors['license']=short_error(e);log(f'WARN license lookup failed for {name}:{tag}: {e}')   # the scan itself succeeded
  else:
   if lic:out.update(license=lic,license_of=where)
 if errors:out['errors']=errors
 return out
def annotate(deps,tags_of=tags_of,scan=scan,cache=CACHE,log=warn,workers=None,is_public=public_host,resolve=version_of,license_of=None):
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
  rows.append((d,(canonical(name),tag)))
 todo=sorted({k for _,k in rows if k not in cache})
 with ThreadPoolExecutor(max_workers=workers or settings.get('images','workers')) as ex:
  for k,res in zip(todo,ex.map(lambda k:lookup(*k,tags_of,scan,log,resolve,license_of),todo)):cache[k]=res
 for d,k in rows:d.update({x:(dict(v) if isinstance(v,dict) else v) for x,v in cache[k].items()})
