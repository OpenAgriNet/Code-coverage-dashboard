"""Load and validate config/repos.json. Every mistake is reported as a ConfigError that names the offending entry."""
import json, re
KINDS=('branch','tag','release')
RELEASE_DEFAULTS={'sources':list(KINDS),'branch_prefix':'release-','tag_pattern':r'^v?(?P<version>\d+(?:\.\d+)*(?:-[0-9A-Za-z.]+)?)$','include_prereleases':True,'max_versions':10}
SOURCE_REQUIRED={'query':'query','project':'number'}
LEGACY={'dpg_repositories':'a source with "fallback"','dpg_project':'a {"type": "project"} source','dpg_source':'a source "note"','exclude_repositories':'"exclude"','release_branch_prefix':'"releases": {"branch_prefix": ...}'}

class ConfigError(ValueError):pass
def tag_list(entry,where):
 tags=entry.get('tags',[])
 if not isinstance(tags,list) or not all(isinstance(t,str) and t.strip() for t in tags):raise ConfigError(f'{where}: "tags" must be a list of non-empty strings')
 return [t.strip() for t in tags]
def name_list(entry,key,where):
 names=entry.get(key,[])
 if not isinstance(names,list) or not all(isinstance(n,str) and n.strip() for n in names):raise ConfigError(f'{where}: "{key}" must be a list of repository names')
 return [n.strip() for n in names]
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
 e={'name':e} if isinstance(e,str) else e
 if not isinstance(e,dict) or not isinstance(e.get('name'),str) or not e['name'].strip():raise ConfigError(f'repositories[{i}]: needs a "name"')
 where=f'repositories[{i}] ({e["name"]})'
 return {'name':e['name'].strip(),'branch':e.get('branch') or None,'tags':tag_list(e,where),'security_workflow':e.get('security_workflow'),'releases':releases(e.get('releases'),base,where)}
def source(s,i):
 where=f'sources[{i}]'
 if not isinstance(s,dict) or s.get('type') not in SOURCE_REQUIRED:raise ConfigError(f'{where}: "type" must be one of {", ".join(SOURCE_REQUIRED)}')
 if not s.get(SOURCE_REQUIRED[s['type']]):raise ConfigError(f'{where} ({s["type"]}): needs "{SOURCE_REQUIRED[s["type"]]}"')
 return {**s,'tags':tag_list(s,where),'fallback':name_list(s,'fallback',where),'enabled':s.get('enabled',True),'label':f'{s["type"]} source #{i+1}'}
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
 defaults=cfg.get('defaults') or {}
 return {**cfg,'releases':rel,'repositories':repos,'sources':[source(s,i) for i,s in enumerate(cfg.get('sources',[]))],
  'exclude':name_list(cfg,'exclude','config'),'default_security_workflow':defaults.get('security_workflow','security.yml')}
def load(path):
 try:
  with open(path,encoding='utf-8') as f:return normalize(json.load(f))
 except json.JSONDecodeError as e:raise ConfigError(f'{path}: invalid JSON ({e})') from e
