"""Docker images: latest tag, the version behind a floating tag, vulnerabilities and license, each looked up once per run."""
from concurrent.futures import ThreadPoolExecutor
from common.log import warn
from common.safehttp import public_host
from stackinfo.rules.reasons import short_error
from stackinfo.lookups.registry import NAME, TAG, SHAPE, split, canonical, latest_like, tags_of, version_of
from stackinfo.lookups.imagescan import scan, image_license, source_repo
from stackinfo.lookups.projects import project_license
from stackinfo import settings
CACHE={}
def configured(name,key):
 """The value config/repos.json gives this image under dependencies.<key>, whichever way the image is spelled there."""
 return {canonical(k):v for k,v in settings.get(key).items()}.get(canonical(name))
def license_for(name,labels,main,license_of):
 """(license, where, from) for an image, the first that gives one: the license config/repos.json states for it
 (dependencies.image_licenses), its GitHub repository named there (dependencies.image_sources), its own license label, the
 repository its source label names, or the license of its own program inside it (main package). None when none does.
 labels and main are None when the image could not be scanned; the config still applies then."""
 lic=configured(name,'image_licenses')
 if lic:return lic,'config',None
 repo=configured(name,'image_sources')
 if repo:
  lic=license_of(repo)
  if lic:return lic,'repo',f'github.com/{repo}'
 if labels:
  lic,where=image_license(labels,license_of)
  if lic:return lic,where,None
 if main:return main[0],'package',main[1]
 return None
def image_repo(name,labels,main):
 """owner/repo of the image's GitHub repository: the one config/repos.json names, its source label's, or its main Go module's."""
 repo=configured(name,'image_sources') or (labels and source_repo(labels))
 if not repo and main and main[1].startswith('github.com/'):repo='/'.join(main[1].split()[0].split('/')[1:3])
 return repo or None
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
 res=None
 try:res=scan(f'{name}:{tag}')
 except Exception as e:errors['vulns']=short_error(e);log(f'WARN image scan failed for {name}:{tag}: {e}')
 else:
  labels,main=res.pop('labels',{}),res.pop('main',None)
  out['vulns']={'checked_version':tag,'exact':True,**res}
 try:lic=license_for(name,res and labels,res and main,license_of)
 except Exception as e:lic=None;errors['license']=short_error(e);log(f'WARN license lookup failed for {name}:{tag}: {e}')
 if lic:out.update(license=lic[0],license_of=lic[1],**({'license_from':lic[2]} if lic[2] else {}))
 elif res is None and 'license' not in errors:errors['license']=errors['vulns']
 repo=image_repo(name,res and labels,res and main)
 if repo:out['project']=f'github.com/{repo}'   # its GitHub stars, like every other row
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
