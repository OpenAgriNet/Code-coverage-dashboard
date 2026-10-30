"""Docker images: latest tag, the version behind a floating tag, vulnerabilities and license, each looked up once per run."""
from concurrent.futures import ThreadPoolExecutor
from common.log import warn
from common.safehttp import public_host
from stackinfo.rules.reasons import short_error
from stackinfo.lookups.registry import NAME, TAG, SHAPE, split, canonical, latest_like, tags_of, version_of, gone_from_docker_hub, GONE
from stackinfo.lookups.imagescan import scan, image_license, source_repo
from stackinfo.lookups.projects import project_license, license_at as project_license_at
from stackinfo import settings
CACHE={}
def configured(name,key):
 """The value config/dependencies.json gives this image under dependencies.<key>, whichever way the image is spelled there."""
 return {canonical(k):v for k,v in settings.get(key).items()}.get(canonical(name))
def release(version):
 """The release a tag or the version it points at names (7.4.12 of 7.4.12-alpine), or None for latest, alpine, ..."""
 m=SHAPE.fullmatch(str(version or ''))
 return m.group(2) if m else None
def license_for(name,labels,main,license_of,tag=None,resolved=None,at=None):
 """(license, where, from) for an image, the first that gives one: its GitHub repository (dependencies.image_sources names it)
 read at the image's own release when the tag names one (redis 7 is 7.4.12 today: RSALv2 or SSPL, not 7.2's BSD-3-Clause), else
 as it is now; its own license label; the repository its source label names; the license of its own program inside it (main
 package); or for an image on ghcr.io the license of the GitHub repository of the same name (ghcr.io/sunbird-rc/sunbird-rc-core).
 None when none does. labels and main are None when the image could not be scanned. Every license is read, none is stated in config."""
 repo=configured(name,'image_sources');ver=release(resolved) or release(tag)
 if repo:
  lic=ver and at and at(repo,ver)
  if lic:return lic,'repo',f'github.com/{repo} at {ver}'
  lic=license_of(repo)
  if lic:return lic,'repo',f'github.com/{repo}'
 if labels:
  lic,where=image_license(labels,license_of)
  if lic:return lic,where,None
 repo=same_name_repo(name)
 if main:
  # an image that wraps a program (sunbird-rc-keycloak: Keycloak) is also its own repository's code: both licenses apply
  own=repo and len(main)>2 and main[2] and license_of(repo)
  if own and own not in main[0].split(', '):return f'{main[0]}, {own}','package',f'{main[1]} + github.com/{repo}'
  return main[0],'package',main[1]
 if repo:
  lic=license_of(repo)
  if lic:return lic,'repo',f'github.com/{repo}'
 return None
def same_name_repo(name):
 """owner/repo of the GitHub repository named like an image on ghcr.io (GHCR namespaces are GitHub accounts), else None. It may
 not exist (knowledge-provider-ui is built by knowledge-provider): a guess, checked by lookups/repostate.py."""
 host,path=split(name)
 return '/'.join(path.split('/')[:2]) if host=='ghcr.io' and path.count('/')>=1 else None
def image_repo(name,labels,main):
 """owner/repo of the image's GitHub repository: the one config/repos.json names, its source label's, its main Go module's, or for
 an image on ghcr.io the repository of the same name (ghcr.io/openagrinet/knowledge-provider -> OpenAgriNet/knowledge-provider)."""
 repo=configured(name,'image_sources') or (labels and source_repo(labels))
 if not repo and main and main[1].startswith('github.com/'):repo='/'.join(main[1].split()[0].split('/')[1:3])
 return repo or same_name_repo(name) or None
def lookup(name,tag,tags_of,scan,log,resolve=version_of,license_of=None,license_at=None):
 license_of=license_of or project_license;at=license_at or (project_license_at if license_of is project_license else None)
 out={'latest':None,'latest_of':None,'vulns':None};errors={}
 try:
  if SHAPE.fullmatch(tag):
   ts=tags_of(name);out['latest']=latest_like(tag,ts);out['latest_of']='registry'
   if SHAPE.fullmatch(tag).group(2).count('.')<2:   # a partial version (7, 15-alpine): the release it points at today
    v=resolve(name,tag,ts)
    if v:out['resolved']=v
  else:
   # a floating tag (latest): find the version it points at today, then compare that version with the newest
   out['latest_of']='floating';ts=tags_of(name);v=resolve(name,tag,ts)
   if v:out.update(resolved=v,latest=latest_like(v,ts),latest_of='registry')
 except Exception as e:errors['latest']=GONE if gone_from_docker_hub(name) else short_error(e);log(f'WARN registry tags failed for {name}: {e}')
 res=None
 try:res=scan(f'{name}:{tag}')
 except Exception as e:errors['vulns']=GONE if errors.get('latest')==GONE else short_error(e);log(f'WARN image scan failed for {name}:{tag}: {e}')
 else:
  labels,main=res.pop('labels',{}),res.pop('main',None)
  out['vulns']={'checked_version':tag,'exact':True,**res}
 try:lic=license_for(name,res and labels,res and main,license_of,tag,out.get('resolved'),at)
 except Exception as e:lic=None;errors['license']=short_error(e);log(f'WARN license lookup failed for {name}:{tag}: {e}')
 if lic:out.update(license=lic[0],license_of=lic[1],**({'license_from':lic[2]} if lic[2] else {}))
 elif res is None and 'license' not in errors:errors['license']=errors['vulns']
 repo=image_repo(name,res and labels,res and main)
 if repo:out['project']=f'github.com/{repo}'   # its GitHub stars, like every other row
 if repo and repo==same_name_repo(name) and not configured(name,'image_sources') and not (res and source_repo(labels)):
  out['project_of']='same name'   # a guess: dropped when no such repository exists (lookups/repostate.py)
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
