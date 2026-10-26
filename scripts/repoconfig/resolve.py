"""Turn the config into the list of repositories to measure.

Rules when the same repository turns up more than once (names are case-insensitive):
 1. A repo listed under "repositories" is authoritative for its dev_branch and security workflow.
 2. Tags are always merged: its own tags first, then each source's tags in config order.
 3. "exclude" beats everything, including an explicit entry.
 4. Private repos found by a source are skipped (the dashboard is public); explicit entries are always kept.
 5. A source that fails stops the run: a silently shrunk repo list would be published as if it were the truth.
    A source that finds nothing is only a warning.

A repo's Development branch is its dev_branch, else the first branch matching branches.development, else None
(the default branch is used, and branch_source says so)."""
import sys
from . import sources
from .branches import find_development

class SourceError(RuntimeError):pass
def merge_tags(*groups):
 return list(dict.fromkeys(t for g in groups for t in g))
def lookup(src,org,get,project_token,search_get=None):
 if src['type']=='query':return sources.query_repos(src,org,search_get or get)
 return sources.project_repos(src,org,project_token)
def resolve(cfg,org,get,project_token=None,log=lambda m:print(m,file=sys.stderr),search_get=None):
 """[{'name','branch','branch_source','dev_branch','tags','security_workflow','releases'}]: explicit repos first, then discovered ones in source order.
 branch is the Development branch (None means the default branch); branch_source is 'configured', 'pattern' or 'default'.
 search_get, if given, is used for the repository search (a token that can read custom properties); everything else uses get."""
 skip={n.lower() for n in cfg['exclude']};found={}
 def target(name,dev,tags,workflow,explicit,releases):
  return {'name':name,'dev_branch':dev,'tags':list(tags),'security_workflow':workflow or cfg['default_security_workflow'],'releases':releases,'explicit':explicit}
 for r in cfg['repositories']:
  if r['name'].lower() in skip:log(f'config: {r["name"]} is listed and excluded; skipping');continue
  found[r['name'].lower()]=target(r['name'],r['dev_branch'],r['tags'],r['security_workflow'],True,r['releases'])
 for src in cfg['sources']:
  if not src['enabled']:continue
  try:matches=lookup(src,org,get,project_token,search_get)
  except Exception as e:raise SourceError(f'{src["label"]} failed: {e}. Nothing was published; the dashboard keeps its last data.') from e
  log(f'{src["label"]}: {len(matches)} repos'+('' if matches else ' (WARN: found nothing; a renamed property or a typo?)'))
  for m in matches:
   key=m['name'].lower()
   if key in skip:continue
   if m['private'] and key not in found:log(f'{src["label"]}: skipping private repo {m["name"]}');continue
   if key not in found:found[key]=target(m['name'],None,src['tags'],None,False,cfg['releases']);continue
   found[key]['tags']=merge_tags(found[key]['tags'],src['tags'])
 out=[]
 for t in found.values():
  t.pop('explicit')
  if t['dev_branch']:branch,how=t['dev_branch'],'configured'
  else:
   branch=find_development(org,t['name'],cfg['branches']['development'],get,log);how='pattern' if branch else 'default'
  out.append({**t,'branch':branch,'branch_source':how})
 return out
