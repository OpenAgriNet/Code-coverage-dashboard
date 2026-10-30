"""Load and validate config/repos.json. Every mistake is reported as a ConfigError that names the offending entry."""
import json, re
KINDS=('branch','tag','release')
RELEASE_DEFAULTS={'sources':list(KINDS),'branch_prefix':'release-','tag_pattern':r'^v?(?P<version>\d+(?:\.\d+)*(?:-[0-9A-Za-z.]+)?)$','include_prereleases':True,'max_versions':10}
SOURCE_REQUIRED={'query':'query','project':'number'}
SOURCE_KEYS={'query':{'type','query','include_forks','tags','enabled'},'project':{'type','org','number','tags','enabled'}}
REPO_KEYS={'name','dev_branch','tags','security_workflow','releases'}
DEV_BRANCH_DEFAULT=r'^(dev|develop|development)$'
COVERAGE_DEFAULTS={'workflow_names':['CI'],'artifact_name_hints':[]}
LEGACY={'dpg_repositories':'a query source under "sources"','dpg_project':'a {"type": "project"} source','dpg_source':'nothing (delete it)','exclude_repositories':'"exclude"',
 'release_branch_prefix':'"releases": {"branch_prefix": ...}','defaults':'"security": {"workflow": ...}','workflow_names':'"coverage": {"workflow_names": [...]}',
 'artifact_name_hints':'"coverage": {"artifact_name_hints": [...]}'}

class ConfigError(ValueError):pass
def tag_list(entry,where):
 tags=entry.get('tags',[])
 if not isinstance(tags,list) or not all(isinstance(t,str) and t.strip() for t in tags):raise ConfigError(f'{where}: "tags" must be a list of non-empty strings')
 return [t.strip() for t in tags]
def name_list(entry,key,where):
 names=entry.get(key,[])
 if not isinstance(names,list) or not all(isinstance(n,str) and n.strip() for n in names):raise ConfigError(f'{where}: "{key}" must be a list of repository names')
 return [n.strip() for n in names]
STACK_DEFAULTS={
 'ignore_languages':['Markdown','JSON','YAML','TOML','INI','CSV','Text','SVG','XML','Jinja','Smarty','HTML','CSS','SCSS','Shell','Dockerfile','Makefile',
  'AMPL','JSONiq'],  # the last two are stack-analyser reading go.mod and .jq files as other languages
 'ignore_techs':['github','github.actions','github.pages','codecov','bash','docker','eslint','prettier','npm','nodejs','vitest','css','jsx','javascript','typescript','python','golang',
  'openapi','opentelemetry','lucideicons','radixui','shadcn','segment'],
 'max_languages':3,'min_share':0.1,'max_techs':6}
def stack_settings(raw):
 """What counts as the 'main stack': languages and tools to leave out, and how many of each to keep."""
 if raw is None:raw={}
 if not isinstance(raw,dict) or set(raw)-set(STACK_DEFAULTS):raise ConfigError(f'stack: use only the keys {", ".join(STACK_DEFAULTS)}')
 out={**STACK_DEFAULTS,**raw}
 for k in ('ignore_languages','ignore_techs'):out[k]=name_list(out,k,'stack')
 for k in ('max_languages','max_techs'):
  if not isinstance(out[k],int) or isinstance(out[k],bool) or out[k]<1:raise ConfigError(f'stack: "{k}" must be a whole number, 1 or more')
 share=out['min_share']
 if not isinstance(share,(int,float)) or isinstance(share,bool) or not 0<=share<=1:raise ConfigError('stack: "min_share" must be a number from 0 to 1')
 return out
LICENSE_CLASSES=('green','yellow','red')
LICENSE_LABELS={'green':'Preferred','yellow':'Not recommended','red':'Restricted use'}   # what the dashboard calls each list
def license_policy(raw):
 """{'green': [...], 'yellow': [...], 'red': [...], 'labels': {...}}: SPDX ids or patterns such as GPL-*, and the name the
 dashboard shows for each list. The same entry in two lists is an error."""
 if raw is None:raw={}
 if not isinstance(raw,dict) or set(raw)-{*LICENSE_CLASSES,'labels','no_license'}:raise ConfigError(f'licenses: use only the keys {", ".join(LICENSE_CLASSES)}, labels, no_license')
 out={};seen={}
 for c in LICENSE_CLASSES:
  out[c]=name_list(raw,c,'licenses')
  for p in out[c]:
   if seen.setdefault(p.lower(),c)!=c:raise ConfigError(f'licenses: "{p}" is in both {seen[p.lower()]} and {c}')
 labels=raw.get('labels',{})
 if not isinstance(labels,dict) or set(labels)-set(LICENSE_CLASSES) or not all(isinstance(v,str) and v.strip() for v in labels.values()):
  raise ConfigError(f'licenses.labels: map {", ".join(LICENSE_CLASSES)} to the names to show, for example {{"green": "Preferred"}}')
 out['labels']={**LICENSE_LABELS,**{k:v.strip() for k,v in labels.items()}}
 # the class of a dependency or repository that nothing states a license for; None leaves it unclassified
 out['no_license']=raw.get('no_license')
 if out['no_license'] not in (None,*LICENSE_CLASSES):raise ConfigError(f'licenses.no_license must be one of {", ".join(LICENSE_CLASSES)} (or left out)')
 return out
# The dependency scan's settings live in config/dependencies.json (every mapping: image sources and licenses, image kinds, names,
# group aliases, ...). The built-in defaults are only switches and limits, so a missing file means 'everything on, nothing mapped'.
DEPENDENCY_DEFAULTS={
 'checks':{'vulnerabilities':True,'actions':True,'images':True,'terraform':True,'workflow_tools':True,'stars':True},
 'images':{'workers':4,'scan_timeout':900,'max_findings':50,'resolve_limit':30,'max_tag_pages':50},
 'groups':{'aliases':{},'workflow_purposes':{},'default_workflow_group':'ci','by_ecosystem':{}},
 'terraform':{'trusted_registries':[]},
 'license_aliases':{},'ecosystem_names':{},'default_image_kind':'Container','image_sources':{},
}
IMAGE_LIMITS={'workers':(1,16),'scan_timeout':(60,3600),'max_findings':(1,5000),'resolve_limit':(0,200),'max_tag_pages':(1,500)}
def _keys(raw,allowed,where):
 if raw is None:return {}
 if not isinstance(raw,dict):raise ConfigError(f'{where} must be an object')
 unknown=sorted(set(raw)-set(allowed))
 if unknown:raise ConfigError(f'{where}: unknown key(s) {", ".join(unknown)}; allowed: {", ".join(allowed)}')
 return raw
def _text_map(raw,where,lower_keys=False):
 if not isinstance(raw,dict) or not all(isinstance(k,str) and k.strip() and isinstance(v,str) and v.strip() for k,v in raw.items()):
  raise ConfigError(f'{where} must map names to names, for example {{"tests": "test"}}')
 return {(k.strip().lower() if lower_keys else k.strip()):v.strip() for k,v in raw.items()}
GITHUB_REPO=re.compile(r'(?!\.)[A-Za-z0-9_.-]+/(?!\.)[A-Za-z0-9_.-]+')
def _image_sources(raw):
 out=_text_map(raw,'dependencies.image_sources')
 bad=[f'{k}: {v}' for k,v in out.items() if not GITHUB_REPO.fullmatch(v)]
 if bad:raise ConfigError(f'dependencies.image_sources must map an image to a GitHub repository written owner/repo; not: {", ".join(bad)}')
 return out
def _name(v,where):
 if not isinstance(v,str) or not v.strip():raise ConfigError(f'{where} must be a name')
 return v.strip()
def dependency_settings(raw):
 """The dependency scan's switches, limits and names: config/repos.json's "dependencies" block over DEPENDENCY_DEFAULTS."""
 D=DEPENDENCY_DEFAULTS;raw=_keys(raw,D,'dependencies')
 checks={**D['checks'],**_keys(raw.get('checks'),D['checks'],'dependencies.checks')}
 for k,v in checks.items():
  if not isinstance(v,bool):raise ConfigError(f'dependencies.checks.{k} must be true or false')
 images={**D['images'],**_keys(raw.get('images'),D['images'],'dependencies.images')}
 for k,(lo,hi) in IMAGE_LIMITS.items():
  v=images[k]
  if not isinstance(v,int) or isinstance(v,bool) or not lo<=v<=hi:raise ConfigError(f'dependencies.images.{k} must be a whole number from {lo} to {hi}')
 g=_keys(raw.get('groups'),D['groups'],'dependencies.groups')
 groups={'aliases':_text_map(g.get('aliases',D['groups']['aliases']),'dependencies.groups.aliases',lower_keys=True),
  'by_ecosystem':_text_map(g.get('by_ecosystem',D['groups']['by_ecosystem']),'dependencies.groups.by_ecosystem'),
  'workflow_purposes':_text_map(g.get('workflow_purposes',D['groups']['workflow_purposes']),'dependencies.groups.workflow_purposes',lower_keys=True),
  'default_workflow_group':g.get('default_workflow_group',D['groups']['default_workflow_group'])}
 if not isinstance(groups['default_workflow_group'],str) or not groups['default_workflow_group'].strip():raise ConfigError('dependencies.groups.default_workflow_group must be a group name')
 tf={**D['terraform'],**_keys(raw.get('terraform'),D['terraform'],'dependencies.terraform')}
 tf['trusted_registries']=name_list(tf,'trusted_registries','dependencies.terraform')
 return {'checks':checks,'images':images,'groups':groups,'terraform':tf,
  'license_aliases':_text_map(raw.get('license_aliases',D['license_aliases']),'dependencies.license_aliases',lower_keys=True),
  'ecosystem_names':{**D['ecosystem_names'],**_text_map(raw.get('ecosystem_names',{}),'dependencies.ecosystem_names')},
  'default_image_kind':_name(raw.get('default_image_kind',D['default_image_kind']),'dependencies.default_image_kind'),
  'image_sources':_image_sources(raw.get('image_sources',{}))}
def releases(raw,base,where):
 """Effective release-finding settings: `base` (or the defaults) overridden by `raw`. None when `raw` is false (releases off)."""
 if raw is False:return None
 if raw is None:return base
 if not isinstance(raw,dict):raise ConfigError(f'{where}: "releases" must be an object or false')
 unknown=sorted(set(raw)-set(RELEASE_DEFAULTS))
 if unknown:raise ConfigError(f'{where}: unknown releases setting(s) {", ".join(unknown)}; allowed: {", ".join(RELEASE_DEFAULTS)}')
 r={**(base or RELEASE_DEFAULTS),**raw};w=f'{where}: releases'
 if not isinstance(r['sources'],list) or not r['sources'] or len(set(r['sources']))!=len(r['sources']) or not set(r['sources'])<=set(KINDS):raise ConfigError(f'{w}.sources must be a non-empty list from {", ".join(KINDS)} without repeats')
 if not isinstance(r['branch_prefix'],str) or not r['branch_prefix']:raise ConfigError(f'{w}.branch_prefix must be a non-empty string')
 try:ok='version' in re.compile(r['tag_pattern']).groupindex
 except (re.error,TypeError) as e:raise ConfigError(f'{w}.tag_pattern is not a valid regex ({e})') from e
 if not ok:raise ConfigError(f'{w}.tag_pattern needs a named group (?P<version>...)')
 if not isinstance(r['include_prereleases'],bool):raise ConfigError(f'{w}.include_prereleases must be true or false')
 if not isinstance(r['max_versions'],int) or isinstance(r['max_versions'],bool) or r['max_versions']<1:raise ConfigError(f'{w}.max_versions must be a whole number, 1 or more')
 return r
def repository(e,i,base):
 """A custom addition or override. A repo the sources already find only needs an entry to set dev_branch, tags, security_workflow or releases."""
 e={'name':e} if isinstance(e,str) else e
 if not isinstance(e,dict) or not isinstance(e.get('name'),str) or not e['name'].strip():raise ConfigError(f'repositories[{i}]: needs a "name"')
 where=f'repositories[{i}] ({e["name"]})'
 if 'branch' in e:raise ConfigError(f'{where}: "branch" is no longer used. Main is the default branch and Development comes from the dashboard switch; set "dev_branch" if this repo\'s development branch has an unusual name')
 unknown=sorted(set(e)-REPO_KEYS)
 if unknown:raise ConfigError(f'{where}: unknown key(s) {", ".join(unknown)}; allowed: {", ".join(sorted(REPO_KEYS))}')
 dev=e.get('dev_branch')
 if dev is not None and (not isinstance(dev,str) or not dev.strip()):raise ConfigError(f'{where}: "dev_branch" must be a branch name')
 return {'name':e['name'].strip(),'dev_branch':dev.strip() if dev else None,'tags':tag_list(e,where),'security_workflow':e.get('security_workflow'),'releases':releases(e.get('releases'),base,where)}
def source(s,i):
 where=f'sources[{i}]'
 if not isinstance(s,dict) or s.get('type') not in SOURCE_REQUIRED:raise ConfigError(f'{where}: "type" must be one of {", ".join(SOURCE_REQUIRED)}')
 for k,hint in (('fallback','If a source fails the refresh now stops with an error and the dashboard keeps its last data; use "exclude" to drop repos'),('branch','Branches are not set per source; use dev_branch on a repository')):
  if k in s:raise ConfigError(f'{where} ({s["type"]}): "{k}" is no longer used. {hint}')
 unknown=sorted(set(s)-SOURCE_KEYS[s['type']])
 if unknown:raise ConfigError(f'{where} ({s["type"]}): unknown key(s) {", ".join(unknown)}; allowed: {", ".join(sorted(SOURCE_KEYS[s["type"]]))}')
 if not s.get(SOURCE_REQUIRED[s['type']]):raise ConfigError(f'{where} ({s["type"]}): needs "{SOURCE_REQUIRED[s["type"]]}"')
 return {**s,'tags':tag_list(s,where),'enabled':s.get('enabled',True),'label':f'{s["type"]} source #{i+1}'}
def branches_settings(raw):
 """{'development': regex}: which branch is a repo's development branch when the config does not say."""
 if raw is None:raw={}
 if not isinstance(raw,dict) or set(raw)-{'development'}:raise ConfigError('branches: use only the key "development"')
 pattern=raw.get('development',DEV_BRANCH_DEFAULT)
 try:re.compile(pattern)
 except (re.error,TypeError) as e:raise ConfigError(f'branches.development is not a valid regex ({e})') from e
 return {'development':pattern}
def coverage_settings(raw):
 if raw is None:raw={}
 if not isinstance(raw,dict) or set(raw)-set(COVERAGE_DEFAULTS):raise ConfigError(f'coverage: use only the keys {", ".join(COVERAGE_DEFAULTS)}')
 out={**COVERAGE_DEFAULTS,**raw}
 for k in COVERAGE_DEFAULTS:
  if not isinstance(out[k],list) or not all(isinstance(x,str) and x.strip() for x in out[k]):raise ConfigError(f'coverage: "{k}" must be a list of names')
 return out
def security_settings(raw):
 if raw is None:raw={}
 if not isinstance(raw,dict) or set(raw)-{'workflow'}:raise ConfigError('security: use only the key "workflow"')
 w=raw.get('workflow','security.yml')
 if not isinstance(w,str) or not w.strip():raise ConfigError('security: "workflow" must be a workflow file name')
 return {'workflow':w.strip()}
def release_sets(raw):
 """[{'alias','label','current','tags': {repo: tag}}] in the order given. At most one set is marked current."""
 if raw is None:raw=[]
 if not isinstance(raw,list):raise ConfigError('release_sets must be a list of {"alias", "tags"} objects')
 out=[];seen=set()
 for i,s in enumerate(raw):
  w=f'release_sets[{i}]'
  if not isinstance(s,dict) or not isinstance(s.get('alias'),str) or not s['alias'].strip():raise ConfigError(f'{w}: needs an "alias" such as "v1"')
  unknown=sorted(set(s)-{'alias','label','current','tags'})
  if unknown:raise ConfigError(f'{w} ({s["alias"]}): unknown key(s) {", ".join(unknown)}; allowed: alias, label, current, tags')
  alias=s['alias'].strip();w=f'release_sets[{i}] ({alias})'
  if alias.lower() in seen:raise ConfigError(f'{w}: alias used twice (aliases are case-insensitive)')
  seen.add(alias.lower())
  tags=s.get('tags')
  if not isinstance(tags,dict) or not tags or not all(isinstance(k,str) and k.strip() and isinstance(v,str) and v.strip() for k,v in tags.items()):raise ConfigError(f'{w}: "tags" must map repository names to a tag, for example {{"network-adapter": "0.1.0"}}')
  if len({k.lower() for k in tags})!=len(tags):raise ConfigError(f'{w}: a repository is listed twice in "tags"')
  if not isinstance(s.get('current',False),bool):raise ConfigError(f'{w}: "current" must be true or false')
  out.append({'alias':alias,'label':str(s.get('label') or alias),'current':bool(s.get('current',False)),'tags':{k.strip():v.strip() for k,v in tags.items()}})
 if sum(x['current'] for x in out)>1:raise ConfigError('release_sets: more than one set is marked "current": true')
 return out
def normalize(cfg):
 """Validated copy of the config with defaults filled in."""
 if not isinstance(cfg,dict):raise ConfigError('config must be a JSON object')
 for k,hint in LEGACY.items():
  if k in cfg:raise ConfigError(f'"{k}" is no longer used; use {hint} (see README, "Choosing repositories")')
 rel=releases(cfg.get('releases'),dict(RELEASE_DEFAULTS),'config')
 repos=[repository(e,i,rel) for i,e in enumerate(cfg.get('repositories',[]))]
 seen={}
 for r in repos:
  if r['name'].lower() in seen:raise ConfigError(f'repositories: "{r["name"]}" is listed twice (names are case-insensitive); merge the entries')
  seen[r['name'].lower()]=r
 sec=security_settings(cfg.get('security'))
 return {**cfg,'dependencies':dependency_settings(cfg.get('dependencies')),'stack':stack_settings(cfg.get('stack')),'licenses':license_policy(cfg.get('licenses')),'releases':rel,'repositories':repos,'sources':[source(s,i) for i,s in enumerate(cfg.get('sources',[]))],
  'exclude':name_list(cfg,'exclude','config'),'branches':branches_settings(cfg.get('branches')),'coverage':coverage_settings(cfg.get('coverage')),'security':sec,
  'release_sets':release_sets(cfg.get('release_sets')),'default_security_workflow':sec['workflow']}
def drop_notes(v):
 """The value without its notes: keys starting with _ document the file and are not settings."""
 if isinstance(v,dict):return {k:drop_notes(x) for k,x in v.items() if not str(k).startswith('_')}
 return v
def _read(path):
 try:
  with open(path,encoding='utf-8') as f:return json.load(f)
 except json.JSONDecodeError as e:raise ConfigError(f'{path}: invalid JSON ({e})') from e
DEPENDENCIES_FILE='dependencies.json'   # next to repos.json
def load_dependencies(path):
 """The validated settings of a dependencies.json; the built-in defaults when the file does not exist."""
 import os
 if not os.path.exists(path):return dependency_settings(None)
 try:return dependency_settings(drop_notes(_read(path)))
 except ConfigError as e:raise ConfigError(f'{path}: {e}') from e
def load(path):
 """config/repos.json, with the dependency scan's settings from config/dependencies.json beside it."""
 import os
 cfg=_read(path)
 if isinstance(cfg,dict) and 'dependencies' in cfg:
  raise ConfigError(f'{path}: "dependencies" moved to {DEPENDENCIES_FILE} beside it; put image sources, licenses, kinds and the other scan settings there')
 out=normalize(cfg)
 out['dependencies']=load_dependencies(os.path.join(os.path.dirname(path),DEPENDENCIES_FILE))
 return out
