"""Whether each dependency's GitHub repository is archived (read-only, no longer maintained: minio/minio) or does not exist, asked
in one GraphQL request per 50 repositories and cached for the run. A repository only guessed from an image's name
(project_of 'same name') that does not exist is dropped, so the row links nowhere wrong. A failed lookup changes nothing."""
import json
from common import github
from common.log import warn
from stackinfo.lookups.stars import source_repo
STATE={}   # owner/repo (lower case) -> 'archived' | 'active' | 'missing'
BATCH=50

def graphql(query):
 r=github.S.post(github.API+'/graphql',json={'query':query},timeout=45)
 r.raise_for_status();return r.json()
def lookup(repos,post=graphql):
 """Fill STATE for repos not looked up yet."""
 todo=sorted({r.lower() for r in repos}-set(STATE))
 for i in range(0,len(todo),BATCH):
  part=todo[i:i+BATCH]
  q='query{'+' '.join(f'r{j}:repository(owner:{json.dumps(r.split("/")[0])},name:{json.dumps(r.split("/")[1])}){{isArchived}}' for j,r in enumerate(part))+'}'
  data=(post(q) or {}).get('data') or {}
  for j,r in enumerate(part):
   got=data.get(f'r{j}')
   STATE[r]='missing' if got is None else 'archived' if got.get('isArchived') else 'active'
def annotate(deps,post=graphql,log=warn):
 """Add archived: true to every dependency whose repository is archived; drop a guessed project that does not exist."""
 repo_of={id(d):source_repo(d) for d in deps}
 try:lookup([r for r in repo_of.values() if r],post)
 except Exception as e:log(f'WARN repository state lookup failed: {e}')
 for d in deps:
  st=STATE.get((repo_of[id(d)] or '').lower())
  if st=='archived':d['archived']=True
  elif st=='missing' and d.get('project_of')=='same name':d.pop('project',None);d.pop('stars',None);d.pop('stars_of',None)
  d.pop('project_of',None)
