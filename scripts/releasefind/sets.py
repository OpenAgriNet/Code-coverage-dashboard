"""Named release sets: an alias such as v1 maps each repo to its own tag. Matched here to the versions that discovery found."""
from repoconfig.config import RELEASE_DEFAULTS
from .versions import parse

def identity(name,rcfg):
 """The comparable identity of a version, a tag or a release-branch name (v0.1.0, 0.1.0 and release-0.1.0 are one), or None."""
 p=parse('tag',name,rcfg) or parse('branch',name,rcfg)
 return p['identity'] if p else None
def resolve_sets(sets,groups,rcfgs):
 """[{'alias','label','current','repos': {repo: {'tag','version'}}}]. version is the dashboard's version string for that tag,
 or None when discovery did not find it (not a version name, older than max_versions, repo has no releases).
 The current set is the one marked current, else the last one listed."""
 by_repo={g['repository'].lower():g for g in groups}
 cur=next((i for i,s in enumerate(sets) if s['current']),len(sets)-1)
 out=[]
 for i,s in enumerate(sets):
  repos={}
  for name,tag in s['tags'].items():
   g=by_repo.get(name.lower());rc=rcfgs.get(name.lower()) or RELEASE_DEFAULTS;want=identity(tag,rc);version=None
   if g and want:
    version=next((v['version'] for v in g['versions'] if identity(v['version'],RELEASE_DEFAULTS)==want),None)  # discovered versions are canonical (1.2.3), read with the default pattern
   repos[g['repository'] if g else name]={'tag':tag,'version':version}
  out.append({'alias':s['alias'],'label':s['label'],'current':i==cur,'repos':repos})
 return out
