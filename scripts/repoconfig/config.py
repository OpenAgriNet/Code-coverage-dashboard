"""Load and validate config/repos.json. Every mistake is reported as a ConfigError that names the offending entry."""
import json
SOURCE_REQUIRED={'query':'query','project':'number'}
LEGACY={'dpg_repositories':'a source with "fallback"','dpg_project':'a {"type": "project"} source','dpg_source':'a source "note"','exclude_repositories':'"exclude"'}

class ConfigError(ValueError):pass
def tag_list(entry,where):
 tags=entry.get('tags',[])
 if not isinstance(tags,list) or not all(isinstance(t,str) and t.strip() for t in tags):raise ConfigError(f'{where}: "tags" must be a list of non-empty strings')
 return [t.strip() for t in tags]
def name_list(entry,key,where):
 names=entry.get(key,[])
 if not isinstance(names,list) or not all(isinstance(n,str) and n.strip() for n in names):raise ConfigError(f'{where}: "{key}" must be a list of repository names')
 return [n.strip() for n in names]
def repository(e,i):
 e={'name':e} if isinstance(e,str) else e
 if not isinstance(e,dict) or not isinstance(e.get('name'),str) or not e['name'].strip():raise ConfigError(f'repositories[{i}]: needs a "name"')
 where=f'repositories[{i}] ({e["name"]})'
 return {'name':e['name'].strip(),'branch':e.get('branch') or None,'tags':tag_list(e,where),'security_workflow':e.get('security_workflow')}
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
 repos=[repository(e,i) for i,e in enumerate(cfg.get('repositories',[]))]
 seen={}
 for r in repos:
  if r['name'].lower() in seen:raise ConfigError(f'repositories: "{r["name"]}" is listed twice (names are case-insensitive); merge the entries')
  seen[r['name'].lower()]=r
 defaults=cfg.get('defaults') or {}
 return {**cfg,'repositories':repos,'sources':[source(s,i) for i,s in enumerate(cfg.get('sources',[]))],
  'exclude':name_list(cfg,'exclude','config'),'default_security_workflow':defaults.get('security_workflow','security.yml')}
def load(path):
 try:
  with open(path,encoding='utf-8') as f:return normalize(json.load(f))
 except json.JSONDecodeError as e:raise ConfigError(f'{path}: invalid JSON ({e})') from e
