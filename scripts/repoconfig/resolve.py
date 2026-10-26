"""Turn the config into the list of repositories to measure.

Rules when the same repository turns up more than once (names are case-insensitive):
 1. A repo listed under "repositories" is authoritative for its branch and security workflow.
 2. Tags are always merged: its own tags first, then each source's tags in config order.
 3. Between sources, the first one that sets a branch wins; a different branch from a later source is logged.
 4. "exclude" beats everything, including an explicit entry.
 5. Private repos found by a source are skipped (the dashboard is public); explicit entries are always kept.
 6. A source that fails (or is disabled) never stops the others; its "fallback" names are used instead of a failure."""
import sys
from . import sources

def merge_tags(*groups):
 return list(dict.fromkeys(t for g in groups for t in g))
def lookup(src,org,get,project_token):
 if src['type']=='query':return sources.query_repos(src,org,get)
 return sources.project_repos(src,org,project_token)
def resolve(cfg,org,get,project_token=None,log=lambda m:print(m,file=sys.stderr)):
 """[{'name','branch','tags','security_workflow'}]: explicit repos first, then discovered ones in source order."""
 skip={n.lower() for n in cfg['exclude']};found={}
 def target(name,branch,tags,workflow,explicit):
  return {'name':name,'branch':branch,'tags':list(tags),'security_workflow':workflow or cfg['default_security_workflow'],'explicit':explicit}
 for r in cfg['repositories']:
  if r['name'].lower() in skip:log(f'config: {r["name"]} is listed and excluded; skipping');continue
  found[r['name'].lower()]=target(r['name'],r['branch'],r['tags'],r['security_workflow'],True)
 for src in cfg['sources']:
  if not src['enabled']:continue
  try:matches=lookup(src,org,get,project_token);log(f'{src["label"]}: {len(matches)} repos')
  except Exception as e:
   matches=[{'name':n,'private':False} for n in src['fallback']]
   log(f'WARN {src["label"]}: {e}; '+(f'using its {len(matches)} fallback repos' if matches else 'no fallback configured'))
  for m in matches:
   key=m['name'].lower()
   if key in skip:continue
   if m['private'] and key not in found:log(f'{src["label"]}: skipping private repo {m["name"]}');continue
   if key not in found:found[key]=target(m['name'],src.get('branch'),src['tags'],None,False);continue
   t=found[key];t['tags']=merge_tags(t['tags'],src['tags'])
   if src.get('branch') and not t['explicit']:
    if t['branch'] is None:t['branch']=src['branch']
    elif t['branch']!=src['branch']:log(f'clash: {t["name"]} branch {t["branch"]!r} kept over {src["branch"]!r} from {src["label"]}')
 return [{k:v for k,v in t.items() if k!='explicit'} for t in found.values()]
